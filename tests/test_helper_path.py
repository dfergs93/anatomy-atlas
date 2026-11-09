import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"


def imported_modules(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_helper_path_needs_only_requirements():
    allowed = {line.strip().split(">")[0].split("=")[0].split("<")[0].lower()
               for line in (REPO / "requirements.txt").read_text().splitlines()
               if line.strip() and not line.startswith("#")}
    seen, todo, outside = set(), ["serve", "share_case"], set()
    while todo:
        mod = todo.pop()
        if mod in seen:
            continue
        seen.add(mod)
        for name in imported_modules(TOOLS / f"{mod}.py"):
            if (TOOLS / f"{name}.py").exists():
                todo.append(name)
            elif name not in sys.stdlib_module_names and name.lower() not in allowed:
                outside.add(name)
    assert outside == set()
