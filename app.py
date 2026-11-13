import sys
from pathlib import Path
root_dir = Path(__file__).parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
exec(open(src_dir / "cogsd_escala" / "app.py", encoding="utf-8").read())
