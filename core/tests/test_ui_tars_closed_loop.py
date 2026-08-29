import unittest
import os
import tempfile
from PIL import Image, ImageDraw
import numpy as np

from tools.gui.tars_closed_loop_runtime import (
    smart_resize_factors,
    denormalize_coordinates,
    crop_zoom_region,
    reproject_cropped_coordinates,
    calculate_screen_delta,
    AdaptiveSettler,
    ClosedLoopGUIAgent,
)
from tools.gui.episodic_trajectory_store import EpisodicTrajectoryStore


class TestUITARSClosedLoop(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.trajectory_store = EpisodicTrajectoryStore(db_path=self.temp_db.name)
        self.agent = ClosedLoopGUIAgent(trajectory_db_path=self.temp_db.name)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_smart_resize_factors_patch_alignment(self):
        """Verify smart_resize_factors produces dimensions divisible by factor (28)."""
        w, h = smart_resize_factors(1920, 1080, factor=28)
        self.assertEqual(w % 28, 0, f"Width {w} must be divisible by 28")
        self.assertEqual(h % 28, 0, f"Height {h} must be divisible by 28")

        # Test 4K resolution clamping
        w_4k, h_4k = smart_resize_factors(3840, 2160, max_pixels=1350 * 28 * 28, factor=28)
        self.assertEqual(w_4k % 28, 0)
        self.assertEqual(h_4k % 28, 0)
        self.assertLessEqual(w_4k * h_4k, 1350 * 28 * 28)

    def test_denormalize_coordinates_resolutions(self):
        """Test coordinate denormalization from [0, 1000] to various screen sizes."""
        # Center of 1920x1080
        cx, cy = denormalize_coordinates(500.0, 500.0, 1920, 1080)
        self.assertEqual((cx, cy), (960, 540))

        # Top-left corner
        tlx, tly = denormalize_coordinates(0.0, 0.0, 1920, 1080)
        self.assertEqual((tlx, tly), (0, 0))

        # Bottom-right corner with clamping
        brx, bry = denormalize_coordinates(1000.0, 1000.0, 1920, 1080)
        self.assertEqual((brx, bry), (1919, 1079))

        # Retina display (2.0 DPI scale)
        rx, ry = denormalize_coordinates(500.0, 500.0, 1920, 1080, dpi_scale=2.0)
        self.assertEqual((rx, ry), (1919, 1079))

    def test_crop_zoom_region_and_reprojection(self):
        """Verify dynamic crop-and-zoom and exact coordinate re-projection."""
        base_img = Image.new("RGB", (1920, 1080), color=(255, 255, 255))
        draw = ImageDraw.Draw(base_img)
        draw.rectangle([490, 390, 510, 410], fill=(255, 0, 0))

        zoomed_img, crop_bbox = crop_zoom_region(base_img, (500, 400), crop_size=(360, 240), zoom_factor=2.0)
        
        left, top, right, bottom = crop_bbox
        self.assertEqual(right - left, 360)
        self.assertEqual(bottom - top, 240)
        self.assertLessEqual(left, 500)
        self.assertGreaterEqual(right, 500)

        reprojected_x, reprojected_y = reproject_cropped_coordinates(500.0, 500.0, crop_bbox)
        self.assertEqual((reprojected_x, reprojected_y), (500, 400))

    def test_calculate_screen_delta(self):
        """Test normalized perceptual screen delta calculation."""
        img1 = Image.new("RGB", (800, 600), color=(0, 0, 0))
        img2 = Image.new("RGB", (800, 600), color=(0, 0, 0))
        
        delta_zero = calculate_screen_delta(img1, img2)
        self.assertEqual(delta_zero, 0.0)

        draw = ImageDraw.Draw(img2)
        draw.rectangle([100, 100, 700, 500], fill=(255, 255, 255))
        delta_mod = calculate_screen_delta(img1, img2)
        self.assertGreater(delta_mod, 10.0)

        self.assertEqual(calculate_screen_delta(None, img1), 100.0)

    def test_system2_prediction_parsing(self):
        """Test parsing of System-2 reasoning blocks and atomic actions."""
        raw_vlm_output = """```
Thought:
- Observation: Dashboard displays a 'Save Settings' button at the bottom right.
- Reflection: Previous modal transition succeeded (delta 18.2%).
- Target Element: 'Save Settings' primary button.
- Next Action: Click save button to persist configuration.
Action: click(start_box='[800, 850, 840, 950]')
```"""
        parsed = self.agent.parse_prediction(raw_vlm_output, (1920, 1080))
        
        self.assertEqual(parsed["action_type"], "click")
        self.assertIn("Save Settings", parsed["thought"])
        self.assertEqual(parsed["bounding_box"], (800.0, 850.0, 840.0, 950.0))
        self.assertEqual(parsed["coords"], (1728, 885))

    def test_type_and_hotkey_parsing(self):
        """Test parsing of type, hotkey, scroll, and terminal actions."""
        p_type = self.agent.parse_prediction("Action: type(content='TARS Scout\\n')", (1920, 1080))
        self.assertEqual(p_type["action_type"], "type")
        self.assertEqual(p_type["content"], "TARS Scout\\n")

        p_hotkey = self.agent.parse_prediction("Action: hotkey(key='ctrl+c')", (1920, 1080))
        self.assertEqual(p_hotkey["action_type"], "hotkey")
        self.assertEqual(p_hotkey["content"], "ctrl+c")

        p_scroll = self.agent.parse_prediction("Action: scroll(start_box='[0, 0, 500, 500]', direction='up')", (1920, 1080))
        self.assertEqual(p_scroll["action_type"], "scroll")
        self.assertEqual(p_scroll["direction"], "up")

        p_finished = self.agent.parse_prediction("Action: finished()", (1920, 1080))
        self.assertEqual(p_finished["action_type"], "finished")

    def test_episodic_trajectory_store_crud(self):
        """Test Episodic Trajectory Store recording, perceptual dHash, and fuzzy lookup."""
        img = Image.new("RGB", (640, 480), color=(128, 128, 128))
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "NeverMiss AI Login", fill=(255, 255, 255))
        
        state_hash = self.trajectory_store.compute_perceptual_hash(img)
        self.assertEqual(len(state_hash), 16)

        action_data = {
            "action_type": "click",
            "coords": [450, 320],
            "thought": "Click on Login button"
        }

        # Record step
        self.trajectory_store.record_step(
            workflow_name="nevermiss_login",
            step_index=1,
            state_hash=state_hash,
            directive="Click the Login button",
            action=action_data
        )

        # Exact lookup
        hit = self.trajectory_store.lookup_cached_action(
            workflow_name="nevermiss_login",
            state_hash=state_hash,
            directive="Click the Login button"
        )
        self.assertIsNotNone(hit)
        self.assertTrue(hit["_cache_hit"])
        self.assertEqual(hit["coords"], [450, 320])
        self.assertEqual(hit["_hamming_dist"], 0)

        # Slightly modified image (simulate slight font rendering shift)
        img_shift = img.copy()
        draw_shift = ImageDraw.Draw(img_shift)
        draw_shift.point((1, 1), fill=(255, 255, 255))
        shift_hash = self.trajectory_store.compute_perceptual_hash(img_shift)
        
        dist = self.trajectory_store.hamming_distance(state_hash, shift_hash)
        self.assertLessEqual(dist, 4)

        # Fuzzy lookup succeeds
        fuzzy_hit = self.trajectory_store.lookup_cached_action(
            workflow_name="nevermiss_login",
            state_hash=shift_hash,
            directive="Click the Login button",
            max_hamming_dist=4
        )
        self.assertIsNotNone(fuzzy_hit)
        self.assertEqual(fuzzy_hit["coords"], [450, 320])

        # Test stats
        stats = self.trajectory_store.get_stats()
        self.assertEqual(stats["total_cached_steps"], 1)
        self.assertEqual(stats["total_workflows"], 1)

        # Test clear
        self.trajectory_store.clear_workflow("nevermiss_login")
        cleared_hit = self.trajectory_store.lookup_cached_action(
            workflow_name="nevermiss_login",
            state_hash=state_hash,
            directive="Click the Login button"
        )
        self.assertIsNone(cleared_hit)


if __name__ == "__main__":
    unittest.main()
