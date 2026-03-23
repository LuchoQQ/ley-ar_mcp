import sys
from pathlib import Path

# Make src/ importable for pytest without requiring pip install -e .
sys.path.insert(0, str(Path(__file__).parent / "src"))
