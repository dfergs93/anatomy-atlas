import ast
import subprocess
import sys
from pathlib import Path

from test_save_case import make_case

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"


def _const(node):
    return node.value if isinstance(node, ast.Constant) else None


def unencoded_text_calls(path):
    """file:line of every text read/write/open in a module that leaves the encoding to the OS."""
    bad = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        f, kws = node.func, {k.arg for k in node.keywords}
        if isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text"):
            text = True
        elif isinstance(f, ast.Name) and f.id == "open":
            mode = _const(node.args[1]) if len(node.args) > 1 else None
            for k in node.keywords:
                if k.arg == "mode":
                    mode = _const(k.value)
            text = "b" not in (mode or "")
        elif isinstance(f, ast.Attribute) and f.attr == "open":
            # Path.open (text by default); ZipFile.open is binary and takes no mode here
            mode = _const(node.args[0]) if node.args else None
            for k in node.keywords:
                if k.arg == "mode":
                    mode = _const(k.value)
            text = mode is not None and "b" not in mode
        else:
            continue
        if text and "encoding" not in kws:
            bad.append(f"{path.relative_to(REPO)}:{node.lineno}")
    return bad


def test_every_text_read_and_write_in_tools_names_its_encoding():
    bad = [b for p in sorted(TOOLS.rglob("*.py")) for b in unencoded_text_calls(p)]
    assert bad == []


def test_save_twice_round_trips_non_ascii_names_under_cp1252(tmp_path):
    """A Windows helper's default text encoding is cp1252: run the saves in a child
    interpreter whose open()/Path text default is forced to cp1252, as it is there."""
    case = make_case(tmp_path)
    name = "Gerdy’s tubercle — test"
    child = f"""
import builtins, io, json, sys
sys.path[:0] = {[str(TOOLS), str(REPO / 'tests')]!r}
_open = io.open
io.text_encoding = lambda enc, stacklevel=2: "cp1252" if enc is None else enc
def cp1252_open(file, mode="r", buffering=-1, encoding=None, *a, **k):
    if "b" not in mode and encoding in (None, "locale"):
        encoding = "cp1252"
    return _open(file, mode, buffering, encoding, *a, **k)
io.open = builtins.open = cp1252_open
from pathlib import Path
from test_save_case import painted, save
case = Path({str(case)!r})
pts = [{{"id": "trochlea", "name": {name!r}, "xyz_mm": [0, 0, 0]}}]
bm = painted(case)
for _ in range(2):
    save(case.parent.parent, case, bm, {{1: "femur", 2: "tibia"}}, points=pts)
    pts = json.loads((case / "points.json").read_bytes().decode("utf-8"))
print("OK")
"""
    r = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    raw = (case / "points.json").read_bytes()
    assert name in raw.decode("utf-8")
