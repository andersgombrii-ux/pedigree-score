import sys
from pathlib import Path

# Add project root to PYTHONPATH so `src` is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

