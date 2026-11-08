"""Read and tick the structure checklist (checklists/<atlas>.md)."""
import re
from dataclasses import dataclass
from pathlib import Path

_ID = re.compile(r"[a-z0-9_]+")


@dataclass
class Row:
    id: str
    name: str
    type: str
    labelled: bool
    content: bool
    group: str


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def read_checklist(path):
    rows, group = [], ""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            group = line[3:].strip()
        elif line.startswith("|"):
            c = _cells(line)
            if len(c) >= 5 and _ID.fullmatch(c[0]) and c[0] != "id":
                rows.append(Row(c[0], c[1], c[2], c[3] == "[x]", c[4] == "[x]", group))
    return rows


def set_labelled(path, ids):
    """Make the Labelled column exactly `ids`; return how many cells changed."""
    path = Path(path)
    out, changed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if line.startswith("|"):
            c = _cells(line)
            if len(c) >= 5 and _ID.fullmatch(c[0]) and c[0] != "id":
                want = "[x]" if c[0] in ids else "[ ]"
                if c[3] != want:
                    parts = line.split("|")  # ['', id, name, type, labelled, ...]
                    parts[4] = parts[4].replace(c[3], want, 1)
                    line = "|".join(parts)
                    changed += 1
        out.append(line)
    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed
