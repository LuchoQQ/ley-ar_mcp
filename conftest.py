import sys
from pathlib import Path

# Make src/ importable for pytest when the package is not installed via pip install -e .
_src = str(Path(__file__).parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
