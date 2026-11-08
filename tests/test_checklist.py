import difflib
import shutil
from pathlib import Path

import checklist

KNEE = Path(__file__).resolve().parents[1] / "checklists" / "knee.md"


def test_read_checklist_knee():
    rows = checklist.read_checklist(KNEE)
    assert len(rows) == 86
    assert {r.type for r in rows} <= {"R", "P", "E"}
    by_id = {r.id: r for r in rows}
    assert all(by_id[i].type == "E" for i in by_id if i.endswith("_bursa"))
    assert sum(r.type == "E" for r in rows) == 4
    assert by_id["fibula"].type == "R"
    assert by_id["fibula"].group == "Bones and landmarks"


def test_set_labelled_changes_only_those_cells(tmp_path):
    copy = tmp_path / "knee.md"
    shutil.copy(KNEE, copy)
    before = copy.read_text().splitlines()
    assert checklist.set_labelled(copy, {"femur", "acl"}) == 2
    after = copy.read_text().splitlines()
    diff = [d for d in difflib.ndiff(before, after) if d[0] in "+-"]
    assert len(diff) == 4
    assert {r.id for r in checklist.read_checklist(copy) if r.labelled} == {"femur", "acl"}
    for b, a in zip(before, after):
        if b != a:
            assert b.replace("[ ]", "[x]", 1) == a
    assert checklist.set_labelled(copy, {"femur", "acl"}) == 0


def test_set_labelled_unticks_rows_no_longer_listed(tmp_path):
    copy = tmp_path / "knee.md"
    shutil.copy(KNEE, copy)
    checklist.set_labelled(copy, {"femur", "acl"})
    assert checklist.set_labelled(copy, {"femur", "tibia"}) == 2
    assert {r.id for r in checklist.read_checklist(copy) if r.labelled} == {"femur", "tibia"}
