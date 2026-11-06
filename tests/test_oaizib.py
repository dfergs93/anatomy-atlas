import io
import json
import zipfile

import pytest

import oaizib
from atlaslib import register_case

HEADER = ["SubjectID", "CMT-ID", "Path", "MRBarCode", "KneeSide", "KLGrade", "Gender", "Age", "BMI"]


def col(n: int) -> str:
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[n]


def make_xlsx(rows) -> bytes:
    """Minimal xlsx: strings go to sharedStrings, numbers inline, None cells are left out (as Excel does)."""
    shared, sheet_rows = [], []
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, v in enumerate(row):
            ref = f"{col(c)}{r}"
            if v is None:
                continue
            if isinstance(v, str):
                shared.append(v)
                cells.append(f'<c r="{ref}" t="s"><v>{len(shared) - 1}</v></c>')
            else:
                cells.append(f'<c r="{ref}"><v>{v}</v></c>')
        sheet_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    return buf.getvalue()


def row(sid, cmt, kl, gender, age, bmi):
    return [sid, cmt, "0.E.1/x", "0166", 1, kl, gender, age, bmi]


def make_info_zip(tmp_path, train_rows, test_rows):
    p = tmp_path / "info.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("info/subInfo_train.xlsx", make_xlsx([HEADER, *train_rows]))
        z.writestr("info/subInfo_test.xlsx", make_xlsx([HEADER, *test_rows]))
    return p


def test_xlsx_rows_reads_shared_strings_and_numbers():
    rows = oaizib.xlsx_rows(make_xlsx([["a", "b", "c"], ["x", 21.699999999999999, None, "z"]]))
    assert rows[0] == ["a", "b", "c"]
    assert rows[1][0] == "x" and float(rows[1][1]) == pytest.approx(21.7)
    assert rows[1][2] == "" and rows[1][3] == "z"   # left-out cell keeps its column


def test_read_subjects_from_info_zip(tmp_path):
    info = make_info_zip(tmp_path, [row(9208055, "049", 0, 2, 46, "21.699999999999999")],
                         [row(9854269, "414", 0, 1, 54, 21.4)])
    subs = oaizib.read_subjects(info)
    assert [(s.cmt_id, s.split) for s in subs] == [("049", "train"), ("414", "test")]
    s = subs[0]
    assert (s.subject_id, s.kl, s.sex, s.age, round(s.bmi, 1)) == (9208055, 0, "F", 46, 21.7)
    assert subs[1].sex == "M"


def test_blank_cells_are_skipped(tmp_path):
    info = make_info_zip(tmp_path, [
        row(1, "001", 0, 2, None, 22.0),       # blank age
        row(2, "002", 0, 2, 40, None),         # blank BMI
        row(3, "003", "NA", 2, 40, 22.0),      # KL not a number
        row(4, "004", 0, 2, 40, 22.0),
    ], [])
    assert [s.cmt_id for s in oaizib.read_subjects(info)] == ["004"]


def test_candidates_filter(tmp_path):
    info = make_info_zip(tmp_path, [
        row(1, "001", 0, 1, 55, 22.0),    # age 55 kept
        row(2, "002", 0, 1, 56, 22.0),    # 56 dropped
        row(3, "003", 0, 1, 40, 18.5),    # BMI 18.5 kept
        row(4, "004", 0, 1, 40, 25.0),    # 25.0 kept
        row(5, "005", 0, 1, 40, 25.1),    # 25.1 dropped
        row(6, "006", 1, 1, 40, 22.0),    # KL 1 dropped
    ], [row(7, "000", 0, 2, 30, 20.0)])
    assert [s.cmt_id for s in oaizib.candidates(oaizib.read_subjects(info))] == ["000", "001", "003", "004"]


def test_extract_finds_members_in_any_folder(tmp_path):
    z = tmp_path / "images.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("imagesTr/oaizib_049_0000.nii.gz", b"a" * 10)
        f.writestr("deep/x/oaizib_414_0000.nii.gz", b"b" * 20)
        f.writestr("imagesTr/oaizib_001_0000.nii.gz", b"c")
    out = tmp_path / "out"
    got = oaizib.extract(z, {"oaizib_049_0000.nii.gz", "oaizib_414_0000.nii.gz"}, out)
    assert sorted(p.name for p in got) == ["oaizib_049_0000.nii.gz", "oaizib_414_0000.nii.gz"]
    assert (out / "oaizib_414_0000.nii.gz").read_bytes() == b"b" * 20
    assert not (out / "oaizib_001_0000.nii.gz").exists()
    with pytest.raises(FileNotFoundError, match="oaizib_999_0000.nii.gz"):
        oaizib.extract(z, {"oaizib_999_0000.nii.gz"}, out)


def test_remove_candidates_only_touches_candidates(tmp_path):
    for cid, extra in (("cand-049", {"candidate": True}), ("knee-mri", {})):
        (tmp_path / "data" / cid).mkdir(parents=True)
        (tmp_path / "data" / cid / "meta.json").write_text("{}")
        register_case(tmp_path, {"case_id": cid, **extra})
    assert oaizib.remove_candidates(tmp_path) == ["cand-049"]
    assert not (tmp_path / "data" / "cand-049").exists()
    assert (tmp_path / "data" / "knee-mri").exists()
    assert [c["case_id"] for c in json.loads((tmp_path / "data" / "index.json").read_text())] == ["knee-mri"]
