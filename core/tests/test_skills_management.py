import os
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure core is in path
import sys
core_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if core_dir not in sys.path:
    sys.path.insert(0, core_dir)

from tools.infrastructure.api_server import app
from tools.infrastructure.routers.skills import parse_yaml_frontmatter, validate_skill_metadata
from tools.infrastructure.server_deps import verify_authorization

app.dependency_overrides[verify_authorization] = lambda: None
client = TestClient(app)

class TestSkillsManagement:

    def test_parse_yaml_frontmatter(self):
        """Tests parsing different types of frontmatter fields."""
        content = (
            "---\n"
            "kenbun:\n"
            "  mode: prototype\n"
            "  fidelity: high\n"
            "  tech_stack: [html, css, javascript]\n"
            "  discovery_required: false\n"
            "---\n"
            "Content goes here"
        )
        metadata = parse_yaml_frontmatter(content)
        assert "kenbun" in metadata
        assert metadata["kenbun"]["mode"] == "prototype"
        assert metadata["kenbun"]["fidelity"] == "high"
        assert metadata["kenbun"]["tech_stack"] == ["html", "css", "javascript"]
        assert metadata["kenbun"]["discovery_required"] is False

    def test_validate_skill_metadata(self, tmp_path):
        """Tests validation rules for skills."""
        # 1. Missing SKILL.md
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert not is_valid
        assert "Missing" in msg

        # 2. Non-compliant frontmatter
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("No frontmatter here")
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert not is_valid
        assert "start with YAML" in msg

        # 3. Missing kenbun section
        skill_file.write_text("---\nname: my-skill\n---\n")
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert not is_valid
        assert "Missing 'kenbun'" in msg

        # 4. Valid frontmatter
        valid_frontmatter = (
            "---\n"
            "kenbun:\n"
            "  mode: prototype\n"
            "  fidelity: high\n"
            "  tech_stack: [html]\n"
            "  discovery_required: false\n"
            "---\n"
        )
        skill_file.write_text(valid_frontmatter)
        is_valid, msg = validate_skill_metadata(skill_dir)
        assert is_valid
        assert msg == "Valid"

    def test_list_skills_endpoint(self, tmp_path):
        """Tests GET /api/v1/skills endpoint."""
        active_dir = tmp_path / "active"
        optional_dir = tmp_path / "optional"
        active_dir.mkdir()
        optional_dir.mkdir()

        # Create active skill
        s1 = active_dir / "active-skill"
        s1.mkdir()
        (s1 / "SKILL.md").write_text("---\nkenbun:\n  mode: prototype\n  fidelity: high\n  tech_stack: []\n  discovery_required: false\n---\n")

        # Create optional skill
        s2 = optional_dir / "optional-skill"
        s2.mkdir()
        (s2 / "SKILL.md").write_text("---\nkenbun:\n  mode: document\n  fidelity: wireframe\n  tech_stack: []\n  discovery_required: true\n---\n")

        with patch("tools.infrastructure.routers.skills.ACTIVE_SKILLS_DIR", active_dir):
            with patch("tools.infrastructure.routers.skills.OPTIONAL_SKILLS_DIR", optional_dir):
                response = client.get("/api/v1/skills")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                skills = data["skills"]
                assert len(skills) == 2
                
                names = [s["name"] for s in skills]
                assert "active-skill" in names
                assert "optional-skill" in names

    def test_install_skill_endpoint(self, tmp_path):
        """Tests POST /api/v1/skills/install endpoint."""
        active_dir = tmp_path / "active"
        optional_dir = tmp_path / "optional"
        active_dir.mkdir()
        optional_dir.mkdir()

        # Valid skill
        s1 = optional_dir / "valid-skill"
        s1.mkdir()
        (s1 / "SKILL.md").write_text("---\nkenbun:\n  mode: prototype\n  fidelity: high\n  tech_stack: []\n  discovery_required: false\n---\n")
        (s1 / "dummy.txt").write_text("Hello")

        # Invalid skill
        s2 = optional_dir / "invalid-skill"
        s2.mkdir()
        (s2 / "SKILL.md").write_text("---\nname: invalid\n---\n")

        with patch("tools.infrastructure.routers.skills.ACTIVE_SKILLS_DIR", active_dir):
            with patch("tools.infrastructure.routers.skills.OPTIONAL_SKILLS_DIR", optional_dir):
                # 1. Attempt invalid install (no force) -> Expect 400
                res = client.post("/api/v1/skills/install", json={"name": "invalid-skill"})
                assert res.status_code == 400
                assert not (active_dir / "invalid-skill").exists()

                # 2. Attempt invalid install (with force) -> Expect 200
                res = client.post("/api/v1/skills/install", json={"name": "invalid-skill", "force": True})
                assert res.status_code == 200
                assert (active_dir / "invalid-skill").exists()

                # 3. Attempt valid install -> Expect 200
                res = client.post("/api/v1/skills/install", json={"name": "valid-skill"})
                assert res.status_code == 200
                assert (active_dir / "valid-skill").exists()
                assert (active_dir / "valid-skill" / "dummy.txt").read_text() == "Hello"

                # 4. Install non-existent -> Expect 404
                res = client.post("/api/v1/skills/install", json={"name": "ghost-skill"})
                assert res.status_code == 404

    def test_uninstall_skill_endpoint(self, tmp_path):
        """Tests POST /api/v1/skills/uninstall endpoint."""
        active_dir = tmp_path / "active"
        active_dir.mkdir()

        s1 = active_dir / "my-active-skill"
        s1.mkdir()
        (s1 / "SKILL.md").write_text("...")

        with patch("tools.infrastructure.routers.skills.ACTIVE_SKILLS_DIR", active_dir):
            # 1. Uninstall existent -> Expect 200
            res = client.post("/api/v1/skills/uninstall", json={"name": "my-active-skill"})
            assert res.status_code == 200
            assert not s1.exists()

            # 2. Uninstall non-existent -> Expect 404
            res = client.post("/api/v1/skills/uninstall", json={"name": "my-active-skill"})
            assert res.status_code == 404
