import json
import re
from pathlib import Path

import pytest

import checklist

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "labels"
KEYS = {"id", "name", "ta2_name", "region", "reviewed", "description", "normal_values",
        "variants_pitfalls", "radiopaedia_url", "related_structures"}
# The panel is read mid-case: keep each label short, and keep citations in docs/labels/.
MAX_WORDS = 200
YEAR = re.compile(r"\b(19|20)\d\d\b")
LABEL_FILES = sorted(LABELS.glob("*.json"))

# Spec §7.1: the minimum for "it works".
CORE_KNEE = [
    "femur", "tibia", "fibula", "patella",
    "medial_meniscus_anterior_horn", "medial_meniscus_body", "medial_meniscus_posterior_horn",
    "lateral_meniscus_anterior_horn", "lateral_meniscus_body", "lateral_meniscus_posterior_horn",
    "medial_meniscus_posterior_root", "lateral_meniscus_posterior_root",
    "acl", "pcl", "mcl_superficial", "mcl_deep", "lcl",
    "popliteus_tendon", "popliteus", "popliteofibular_ligament", "biceps_femoris_tendon",
    "arcuate_ligament", "ligament_of_humphry", "ligament_of_wrisberg",
]


def checklist_ids(region):
    return {r.id for r in checklist.read_checklist(ROOT / "checklists" / f"{region}.md")}


@pytest.mark.parametrize("path", LABEL_FILES, ids=lambda p: p.stem)
def test_label_file_follows_schema(path):
    L = json.loads(path.read_text(encoding="utf-8"))
    assert set(L) == KEYS
    assert L["id"] == path.stem
    assert L["id"] in checklist_ids(L["region"])
    assert isinstance(L["reviewed"], bool)
    for k in ("name", "ta2_name", "description"):
        assert isinstance(L[k], str) and L[k].strip(), k
    assert isinstance(L["normal_values"], dict)
    assert all(isinstance(k, str) and isinstance(v, str) and v.strip()
               for k, v in L["normal_values"].items())
    assert isinstance(L["variants_pitfalls"], list)
    assert all(isinstance(p, str) and p.strip() for p in L["variants_pitfalls"])
    assert L["radiopaedia_url"].startswith("https://radiopaedia.org/articles/")
    rel = L["related_structures"]
    assert len(rel) == len(set(rel)) and L["id"] not in rel
    assert set(rel) <= checklist_ids(L["region"]), set(rel) - checklist_ids(L["region"])


def panel_text(L):
    return [L["description"], *L["variants_pitfalls"],
            *(f"{k.replace('_', ' ')} {v}" for k, v in L["normal_values"].items())]


@pytest.mark.parametrize("path", LABEL_FILES, ids=lambda p: p.stem)
def test_label_text_is_short_enough_to_read_mid_case(path):
    words = sum(len(s.split()) for s in panel_text(json.loads(path.read_text(encoding="utf-8"))))
    assert words <= MAX_WORDS


@pytest.mark.parametrize("path", LABEL_FILES, ids=lambda p: p.stem)
def test_label_text_carries_no_citations(path):
    cited = [s for s in panel_text(json.loads(path.read_text(encoding="utf-8"))) if YEAR.search(s)]
    assert cited == []


def test_core_knee_set_has_content():
    assert len(CORE_KNEE) == 24 and set(CORE_KNEE) <= checklist_ids("knee")
    missing = [i for i in CORE_KNEE if not (LABELS / f"{i}.json").exists()]
    assert missing == []
