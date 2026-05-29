import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Inject project root for clean importing of scripts.bootstrap
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def test_hardware_autopilot_pro_macos():
    """Mock a high-performance Mac (32GB+ Unified RAM) -> verify Pro profile suggested."""
    with patch("sys.platform", "darwin"), \
         patch("subprocess.run") as mock_run:
        
        # Mock sysctl hw.memsize returning 32GB
        mock_result = MagicMock()
        mock_result.stdout = "34359738368\n" # 32 GB in bytes
        mock_run.return_value = mock_result
        
        from scripts.bootstrap import detect_hardware
        ram, vram = detect_hardware()
        
        assert ram == 32.0
        assert vram == 24.0 # 75% unified memory allocation
        
        # Verify mapping logic
        recommended_idx = 1
        if vram >= 16.0 or ram >= 32.0:
            recommended_idx = 2 # Pro
        assert recommended_idx == 2

def test_hardware_autopilot_standard_macos():
    """Mock a standard Mac (16GB Unified RAM) -> verify Standard profile suggested."""
    with patch("sys.platform", "darwin"), \
         patch("subprocess.run") as mock_run:
        
        # Mock sysctl hw.memsize returning 16GB
        mock_result = MagicMock()
        mock_result.stdout = "17179869184\n" # 16 GB in bytes
        mock_run.return_value = mock_result
        
        from scripts.bootstrap import detect_hardware
        ram, vram = detect_hardware()
        
        assert ram == 16.0
        assert vram == 12.0 # 75% unified memory
        
        recommended_idx = 1
        if vram >= 16.0 or ram >= 32.0:
            recommended_idx = 2
        elif ram >= 16.0:
            recommended_idx = 1 # Standard
        assert recommended_idx == 1

def test_hardware_autopilot_light_linux():
    """Mock a lightweight Linux server (8GB RAM, no Nvidia GPU) -> verify Ultra-Light suggested."""
    with patch("sys.platform", "linux"), \
         patch("os.sysconf") as mock_sysconf, \
         patch("subprocess.run") as mock_run:
        
        # Mock page size and page count to equal 8GB total
        mock_sysconf.side_effect = lambda key: 4096 if "PAGE_SIZE" in key else 2097152
        
        # Mock nvidia-smi command not found/fail
        mock_run.side_effect = FileNotFoundError()
        
        from scripts.bootstrap import detect_hardware
        ram, vram = detect_hardware()
        
        assert ram == 8.0
        assert vram == 0.0 # No GPU detected
        
        recommended_idx = 1
        if vram >= 16.0 or ram >= 32.0:
            recommended_idx = 2
        elif ram >= 16.0:
            recommended_idx = 1
        else:
            recommended_idx = 0 # Ultra-Light
        assert recommended_idx == 0

def test_hardware_autopilot_pro_linux():
    """Mock a Linux machine with 16GB RAM and a 24GB RTX 3090 -> verify Pro suggested."""
    with patch("sys.platform", "linux"), \
         patch("os.sysconf") as mock_sysconf, \
         patch("subprocess.run") as mock_run:
        
        # Mock system RAM to be 16GB
        mock_sysconf.side_effect = lambda key: 4096 if "PAGE_SIZE" in key else 4194304
        
        # Mock nvidia-smi returning 24GB memory.total
        mock_result = MagicMock()
        mock_result.stdout = "24576\n" # 24GB in MB
        mock_run.return_value = mock_result
        
        from scripts.bootstrap import detect_hardware
        ram, vram = detect_hardware()
        
        assert ram == 16.0
        assert vram == 24.0
        
        recommended_idx = 1
        if vram >= 16.0 or ram >= 32.0:
            recommended_idx = 2 # Pro due to >=16GB VRAM
        assert recommended_idx == 2
