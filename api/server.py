"""FastAPI server for the anatomy atlas.

Four endpoints serving slice data, label details, search, and listing.
Mounts the data/ directory as static files for direct PNG serving.

Usage:
    uvicorn api.server:app --reload
    # Or from repo root:
    python -m uvicorn api.server:app --reload
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Anatomy Atlas API",
    description="Cross-sectional anatomy atlas — pre-rendered PNG slices with SVG label overlays",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
LABELS_DIR = BASE_DIR / "labels"

# Mount static files for direct PNG serving
app.mount("/static", StaticFiles(directory=str(DATA_DIR)), name="static")

# ---------------------------------------------------------------------------
# Data loading (cached at startup)
# ---------------------------------------------------------------------------

# In-memory cache of all case metadata and label data
_cases: dict = {}
_labels: dict = {}
_slice_labels: dict = {}  # {case_id: {slice_id: [labels]}}


def _load_data():
    """Load all case metadata and label data into memory."""
    global _cases, _labels, _slice_labels

    # Load case metadata from data/ directories
    if DATA_DIR.exists():
        for case_dir in sorted(DATA_DIR.iterdir()):
            if not case_dir.is_dir():
                continue

            meta_path = case_dir / "meta.json"
            index_path = case_dir / "index.json"

            if not meta_path.exists() or not index_path.exists():
                continue

            with open(meta_path) as f:
                meta = json.load(f)
            with open(index_path) as f:
                index = json.load(f)

            case_id = case_dir.name
            _cases[case_id] = {**meta, **index, "case_id": case_id}

            # Load slice labels
            slices_dir = case_dir / "slices"
            if slices_dir.exists():
                _slice_labels[case_id] = {}
                for labels_file in sorted(slices_dir.glob("*_labels.json")):
                    slice_id = labels_file.stem.replace("_labels", "")
                    with open(labels_file) as f:
                        _slice_labels[case_id][slice_id] = json.load(f)

    # Load label definitions from labels/ directory
    if LABELS_DIR.exists():
        for label_file in sorted(LABELS_DIR.glob("*.json")):
            with open(label_file) as f:
                label_data = json.load(f)
            _labels[label_data["id"]] = label_data


@app.on_event("startup")
async def startup():
    _load_data()


# ---------------------------------------------------------------------------
# Helper to build a directory name from query params
# ---------------------------------------------------------------------------

def _resolve_case_id(body_part: str, modality: str, plane: str) -> Optional[str]:
    """Map query parameters to a case directory name.

    Tries exact match first, then searches metadata.
    """
    # Direct construction based on naming convention
    modality_lower = modality.lower()
    body_lower = body_part.lower()

    # Special case for cardiac
    if body_lower == "cardiac":
        candidate = f"cardiac-cta-{plane.lower()}"
    else:
        candidate = f"{modality_lower}-{body_lower}-{plane.lower()}"

    if candidate in _cases:
        return candidate

    # Search through metadata
    for case_id, meta in _cases.items():
        if (meta.get("body_part", "").lower() == body_lower
                and meta.get("modality", "").upper() == modality.upper()
                and meta.get("plane", "").lower() == plane.lower()):
            return case_id

    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/atlas/list")
async def atlas_list():
    """List all available atlas cases.

    Returns:
        List of case summaries with body_part, modality, plane, canonical_level,
        and structure_count.
    """
    results = []
    for case_id, meta in _cases.items():
        results.append({
            "case_id": case_id,
            "body_part": meta.get("body_part", ""),
            "modality": meta.get("modality", ""),
            "plane": meta.get("plane", ""),
            "canonical_level": meta.get("level", ""),
            "structure_count": len(meta.get("structures", [])),
        })
    return results


@app.get("/atlas/slice")
async def atlas_slice(
    body_part: str = Query(..., description="Body region (e.g., chest, cardiac, abdomen)"),
    modality: str = Query("CT", description="Imaging modality (e.g., CT, MRI)"),
    plane: str = Query("axial", description="Slice plane (axial, coronal, sagittal)"),
):
    """Get slice data for a specific body region.

    Returns URLs for the slice PNG, overlay PNG, and labels JSON,
    along with the anatomical level and source citation.
    """
    case_id = _resolve_case_id(body_part, modality, plane)
    if not case_id:
        raise HTTPException(
            status_code=404,
            detail=f"No atlas case found for body_part={body_part}, modality={modality}, plane={plane}",
        )

    meta = _cases[case_id]
    canonical = meta.get("canonical_slice", "050")

    base_url = f"/static/{case_id}/slices"

    return {
        "case_id": case_id,
        "slice_png_url": f"{base_url}/{canonical}.png",
        "overlay_png_url": f"{base_url}/{canonical}_overlay.png",
        "labels_json_url": f"{base_url}/{canonical}_labels.json",
        "level": meta.get("level", ""),
        "source_citation": meta.get("source", ""),
    }


@app.get("/atlas/label")
async def atlas_label(
    slice_id: str = Query(..., description="Case ID (e.g., ct-chest-axial)"),
    label_id: str = Query(..., description="Structure ID (e.g., left_ventricle)"),
):
    """Get detailed label information for a specific structure.

    Returns the full label content: name, TA2, description, normal values,
    Radiopaedia URL, and related structures.
    """
    # First check the labels/ directory definitions
    if label_id in _labels:
        label = _labels[label_id]
        result = {
            "id": label["id"],
            "name": label["name"],
            "ta2_name": label.get("ta2_name", ""),
            "description": label.get("description", ""),
            "normal_values": label.get("normal_values", {}),
            "radiopaedia_url": label.get("radiopaedia_url", ""),
            "related_structures": label.get("related_structures", []),
        }

        # Add slice-specific polygon if available
        if slice_id in _slice_labels:
            canonical = _cases.get(slice_id, {}).get("canonical_slice", "050")
            if canonical in _slice_labels[slice_id]:
                for sl in _slice_labels[slice_id][canonical]:
                    if sl["id"] == label_id:
                        result["polygon"] = sl.get("polygon", [])
                        break

        return result

    # Fall back to slice-specific label data
    if slice_id in _slice_labels:
        canonical = _cases.get(slice_id, {}).get("canonical_slice", "050")
        if canonical in _slice_labels[slice_id]:
            for sl in _slice_labels[slice_id][canonical]:
                if sl["id"] == label_id:
                    return {
                        "id": sl["id"],
                        "name": sl["name"],
                        "ta2_name": sl.get("ta2", ""),
                        "description": sl.get("description", ""),
                        "normal_values": sl.get("normal_values", {}),
                        "radiopaedia_url": sl.get("radiopaedia_url", ""),
                        "related_structures": [],
                    }

    raise HTTPException(
        status_code=404,
        detail=f"Label '{label_id}' not found in slice '{slice_id}'",
    )


@app.get("/atlas/search")
async def atlas_search(
    q: str = Query(..., min_length=1, description="Search query"),
):
    """Search for structures across all atlas cases.

    Matches against structure name, TA2 name, and description.
    Returns matching structures with their location in the atlas.
    """
    query = q.lower()
    results = []
    seen = set()

    # Search in labels/ definitions
    for label_id, label in _labels.items():
        name = label.get("name", "").lower()
        ta2 = label.get("ta2_name", "").lower()
        desc = label.get("description", "").lower()

        if query in name or query in ta2 or query in desc:
            # Find which cases contain this structure
            for case_id, case_meta in _cases.items():
                if label_id in case_meta.get("structures", []):
                    key = (case_id, label_id)
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            "slice_id": case_id,
                            "label_id": label_id,
                            "name": label["name"],
                            "modality": case_meta.get("modality", ""),
                            "plane": case_meta.get("plane", ""),
                        })

    # Also search slice-specific labels for structures not in labels/
    for case_id, slices in _slice_labels.items():
        case_meta = _cases.get(case_id, {})
        for slice_id, labels_list in slices.items():
            for sl in labels_list:
                name = sl.get("name", "").lower()
                ta2 = sl.get("ta2", "").lower()
                desc = sl.get("description", "").lower()

                if query in name or query in ta2 or query in desc:
                    key = (case_id, sl["id"])
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            "slice_id": case_id,
                            "label_id": sl["id"],
                            "name": sl["name"],
                            "modality": case_meta.get("modality", ""),
                            "plane": case_meta.get("plane", ""),
                        })

    return results


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "cases_loaded": len(_cases),
        "labels_loaded": len(_labels),
    }
