"""QCAD MCP shared helpers: DXF I/O, block search, metadata, depot management."""

import json
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from qcad_mcp.config import DEPOT_DIR, EXT_DXF, OUTPUT_DIR
from qcad_mcp.services import qcad_pro

logger = logging.getLogger("qcad-mcp")


def _get_ezdxf_version() -> str:
    """Return the installed ezdxf version string."""
    try:
        import ezdxf

        return ezdxf.__version__
    except Exception:
        return "unknown"


def _meta_path(filename: str) -> str:
    """Return the path to the metadata JSON file for a given depot filename."""
    return os.path.join(DEPOT_DIR, f"{filename}.meta.json")


def _read_meta(filename: str) -> dict:
    """Read metadata JSON for a depot file. Returns empty dict on failure."""
    mp = _meta_path(filename)
    if os.path.isfile(mp):
        try:
            with open(mp) as f:
                return json.load(f)
        except Exception:
            logger.debug("Failed to read meta for %s", filename, exc_info=True)
    return {}


def _write_meta(filename: str, meta: dict):
    """Write metadata JSON for a depot file."""
    with open(_meta_path(filename), "w") as f:
        json.dump(meta, f, indent=2, default=str)


def _ensure_meta(filename: str):
    """Ensure metadata fields exist, filling in defaults if missing."""
    meta = _read_meta(filename)
    changed = False
    if "created" not in meta:
        meta["created"] = datetime.now().isoformat()
        changed = True
    if "description" not in meta:
        meta["description"] = ""
        changed = True
    if "tags" not in meta:
        meta["tags"] = []
        changed = True
    if changed:
        _write_meta(filename, meta)
    return meta


def _depot_list() -> list[dict]:
    """List all DXF/DWG files in the depot with metadata, sorted by modification time."""
    files = {}
    for f in os.listdir(DEPOT_DIR):
        fp = os.path.join(DEPOT_DIR, f)
        if not os.path.isfile(fp):
            continue
        _base, ext = os.path.splitext(f)
        if ext == ".meta.json":
            continue
        if ext not in EXT_DXF and ext != ".dwg":
            continue
        meta = _ensure_meta(f)
        files[f] = {
            "name": f,
            "size_bytes": os.path.getsize(fp),
            "size_kb": round(os.path.getsize(fp) / 1024, 1),
            "modified": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
            "meta": meta,
        }
    return sorted(files.values(), key=lambda x: x["modified"], reverse=True)


def _load_dxf(file_name: str):
    """Load a DXF file from the depot. Auto-converts DWG via QCAD Pro if needed.

    Returns (doc, error) tuple.
    """
    import ezdxf

    path = os.path.join(DEPOT_DIR, file_name)
    if not os.path.isfile(path):
        return None, f"File '{file_name}' not found in depot."

    # Auto-convert DWG to temp DXF
    if _is_dwg(file_name):
        if not _qcad_pro_available():
            return None, "DWG files require QCAD Pro. Set QCAD_PRO_PATH or convert to DXF first."
        dxf_path = os.path.join(OUTPUT_DIR, Path(file_name).stem + "_converted.dxf")
        if not _qcad_pro_convert(path, dxf_path, "DXF"):
            return None, "QCAD Pro DWG->DXF conversion failed."
        path = dxf_path

    try:
        doc = ezdxf.readfile(path)
        return doc, None
    except Exception as e:
        return None, f"Failed to read DXF: {e}"


def _doc_to_info(doc) -> dict:
    """Extract structured info from an ezdxf document: layers, entities, blocks, bounding box."""
    msp = doc.modelspace()
    entity_counts = {}
    for e in msp:
        entity_counts[e.dxftype()] = entity_counts.get(e.dxftype(), 0) + 1

    layers = []
    for layer in doc.layers:
        layers.append(
            {
                "name": layer.dxf.name,
                "color": layer.dxf.color,
                "frozen": getattr(layer, "is_frozen", lambda: False)(),
                "locked": getattr(layer, "is_locked", lambda: False)(),
            }
        )

    blocks = [b.name for b in doc.blocks]

    bbox = None
    try:
        from ezdxf.bbox import extents

        bbox_rect = extents(msp)
        if bbox_rect.has_data:
            bbox = {
                "xmin": bbox_rect.extmin.x,
                "ymin": bbox_rect.extmin.y,
                "xmax": bbox_rect.extmax.x,
                "ymax": bbox_rect.extmax.y,
            }
    except Exception:
        logger.debug("Failed to compute bounding box", exc_info=True)

    return {
        "layers": layers,
        "layer_count": len(layers),
        "entity_counts": entity_counts,
        "entity_total": sum(entity_counts.values()),
        "blocks": blocks,
        "block_count": len(blocks),
        "bounding_box": bbox,
        "dxf_version": doc.dxfversion,
    }


def _is_dwg(file_name: str) -> bool:
    """Check if a filename has a .dwg extension."""
    return Path(file_name).suffix.lower() == ".dwg"


def _qcad_pro_available() -> bool:
    """Return True if QCAD Pro is installed and reachable."""
    return qcad_pro.is_installed()


def _qcad_pro_convert(input_path: str, output_path: str, fmt: str = "DXF") -> bool:
    """Convert a CAD file using QCAD Pro CLI. Returns True on success."""
    result = qcad_pro.convert(input_path, output_path, fmt)
    return result.get("success", False)


def _ensure_dxf(file_name: str) -> tuple[str | None, str | None]:
    """If DWG, convert to temp DXF. Returns (dxf_path_or_original, error)."""
    if not _is_dwg(file_name):
        return os.path.join(DEPOT_DIR, file_name), None
    if not _qcad_pro_available():
        return None, "DWG files require QCAD Pro. Set QCAD_PRO_PATH or convert to DXF first."
    dwg_path = os.path.join(DEPOT_DIR, file_name)
    dxf_path = os.path.join(OUTPUT_DIR, Path(file_name).stem + "_converted.dxf")
    if _qcad_pro_convert(dwg_path, dxf_path, "DXF"):
        return dxf_path, None
    return None, "QCAD Pro conversion failed. Check the file or QCAD installation."


# ── CAD Block Search ──────────────────────────────────────────────────────────

_BLOCK_CATEGORIES = [
    {"id": "", "label": "All"},
    {"id": "furniture", "label": "Furniture"},
    {"id": "doors-windows", "label": "Doors & Windows"},
    {"id": "kitchens", "label": "Kitchens"},
    {"id": "bathrooms", "label": "Bathrooms"},
    {"id": "lighting", "label": "Lighting"},
    {"id": "electrical", "label": "Electrical"},
    {"id": "plumbing", "label": "Plumbing"},
    {"id": "stairs", "label": "Stairs"},
    {"id": "trees-plants", "label": "Trees & Plants"},
    {"id": "vehicles", "label": "Vehicles"},
    {"id": "people", "label": "People & Scale Figures"},
    {"id": "sports", "label": "Sports & Recreation"},
    {"id": "landscape", "label": "Landscape"},
    {"id": "symbols", "label": "CAD Symbols"},
    {"id": "title-blocks", "label": "Title Blocks"},
    {"id": "tables", "label": "Tables & Chairs"},
    {"id": "beds", "label": "Beds"},
    {"id": "sofas", "label": "Sofas & Seating"},
    {"id": "shelves", "label": "Shelves & Storage"},
    {"id": "office", "label": "Office"},
    {"id": "industrial", "label": "Industrial Equipment"},
    {"id": "machinery", "label": "Machinery"},
    {"id": "floor-plans", "label": "Sample Floor Plans"},
    {"id": "detailing", "label": "Construction Detailing"},
]

_BLOCK_HEADERS = {"User-Agent": "qcad-mcp/0.3.0 (MCP server; +https://github.com/sandraschi/qcad-mcp)"}


async def _search_cadblocksfree(query: str, category: str, limit: int) -> list[dict]:
    """Search cadblocksfree.com for CAD blocks."""
    results = []
    url = (
        f"https://www.cadblocksfree.com/en/search/{query.replace(' ', '-')}/"
        if query
        else "https://www.cadblocksfree.com/en/cad-blocks/"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers=_BLOCK_HEADERS)
            soup = BeautifulSoup(r.text, "html.parser")
            for article in soup.select("article.grid-item, div.portfolio-item, div.cad-item, li.grid-item")[:limit]:
                title_el = article.select_one("h3 a, h2 a, .title a, a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                img_el = article.select_one("img")
                img = img_el.get("src", "") if img_el else ""
                cat_el = article.select_one(".category, .cat, .term")
                cat = cat_el.get_text(strip=True) if cat_el else category or "General"
                results.append(
                    {
                        "title": title[:100],
                        "source": "cadblocksfree",
                        "url": href if href.startswith("http") else f"https://www.cadblocksfree.com{href}",
                        "image_url": img
                        if img.startswith("http")
                        else f"https://www.cadblocksfree.com{img}"
                        if img
                        else "",
                        "category": cat,
                    }
                )
    except Exception as e:
        logger.warning("cadblocksfree search error: %s", e)
    return results


async def _search_biblocad(query: str, category: str, limit: int) -> list[dict]:
    """Search biblocad.com for CAD blocks."""
    results = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(f"https://biblocad.com/search?q={query}", headers=_BLOCK_HEADERS)
            soup = BeautifulSoup(r.text, "html.parser")
            for item in soup.select(".item, .result-item, .search-item, .block-item, tr")[:limit]:
                title_el = item.select_one("a.title, a.name, h3 a, h2 a, td a")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                img_el = item.select_one("img")
                img = img_el.get("src", "") if img_el else ""
                results.append(
                    {
                        "title": title[:100],
                        "source": "biblocad",
                        "url": href if href.startswith("http") else f"https://biblocad.com{href}",
                        "image_url": img if img.startswith("http") else f"https://biblocad.com{img}" if img else "",
                        "category": category or "General",
                    }
                )
    except Exception as e:
        logger.warning("biblocad search error: %s", e)
    return results


async def _search_gallery(query: str, category: str, limit: int) -> list[dict]:
    """Return curated sample floor plans and architectural blocks."""
    samples = {
        "floor-plans": [
            {
                "title": "Small Apartment Floor Plan (45m\u00b2)",
                "url": "https://www.cadblocksfree.com/en/download/small-apartment-plan.dxf",
                "category": "Floor Plans",
            },
            {
                "title": "Office Layout Open Plan",
                "url": "https://www.cadblocksfree.com/en/download/office-open-plan.dxf",
                "category": "Floor Plans",
            },
            {
                "title": "Two-Bedroom House Plan (80m\u00b2)",
                "url": "https://www.cadblocksfree.com/en/download/two-bedroom-house.dxf",
                "category": "Floor Plans",
            },
            {
                "title": "Restaurant Floor Plan",
                "url": "https://www.cadblocksfree.com/en/download/restaurant-plan.dxf",
                "category": "Floor Plans",
            },
            {
                "title": "Classroom Layout",
                "url": "https://www.cadblocksfree.com/en/download/classroom.dxf",
                "category": "Floor Plans",
            },
        ],
        "doors-windows": [
            {"title": "Door Block Collection (20 types)", "category": "Doors & Windows"},
            {"title": "Window Block Collection (15 types)", "category": "Doors & Windows"},
            {"title": "Sliding Door Details", "category": "Doors & Windows"},
            {"title": "French Door Elevation", "category": "Doors & Windows"},
            {"title": "Garage Door Plan View", "category": "Doors & Windows"},
        ],
        "furniture": [
            {"title": "Sofa Collection (10 styles)", "category": "Furniture"},
            {"title": "Dining Table Sets", "category": "Furniture"},
            {"title": "Bedroom Furniture Pack", "category": "Furniture"},
            {"title": "Bookshelf Units", "category": "Furniture"},
            {"title": "Kitchen Cabinet Layouts", "category": "Furniture"},
        ],
        "bathrooms": [
            {"title": "Bathroom Fixture Blocks", "category": "Bathrooms"},
            {"title": "Shower Cubicle Details", "category": "Bathrooms"},
            {"title": "Toilet & Sink Blocks", "category": "Bathrooms"},
            {"title": "Bathtub Collection", "category": "Bathrooms"},
        ],
        "trees-plants": [
            {"title": "Tree Blocks (Plan View)", "category": "Trees & Plants"},
            {"title": "Plant Pot Collection", "category": "Trees & Plants"},
            {"title": "Garden Layout Elements", "category": "Trees & Plants"},
        ],
    }
    if query:
        results = [
            item for cat_items in samples.values() for item in cat_items if query.lower() in item["title"].lower()
        ]
    elif category and category in samples:
        results = samples[category]
    else:
        results = [item for cat_items in samples.values() for item in cat_items]
    for r in results:
        r.setdefault("source", "gallery")
        r.setdefault("image_url", "")
        r.setdefault("url", "")
    return results[:limit]


_BLOCK_SOURCES = {
    "cadblocksfree": _search_cadblocksfree,
    "biblocad": _search_biblocad,
    "gallery": _search_gallery,
}
