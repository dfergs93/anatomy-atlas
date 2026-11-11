import json
from pathlib import Path

import pytest

import checklist

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "labels"
KEYS = {"id", "name", "ta2_name", "region", "reviewed", "description", "normal_values",
        "variants_pitfalls", "radiopaedia_url", "related_structures"}

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


@pytest.mark.parametrize("path", sorted(LABELS.glob("*.json")), ids=lambda p: p.stem)
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


def test_core_knee_set_has_content():
    assert len(CORE_KNEE) == 24 and set(CORE_KNEE) <= checklist_ids("knee")
    missing = [i for i in CORE_KNEE if not (LABELS / f"{i}.json").exists()]
    assert missing == []
