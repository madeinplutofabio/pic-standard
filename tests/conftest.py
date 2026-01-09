import sys
from pathlib import Path

SDK_DIR = Path(__file__).resolve().parents[1] / "sdk-python"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))
