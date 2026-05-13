"""CAD block search tools — search and download architectural blocks from online libraries."""

import logging
import os
from typing import Annotated

import httpx
from bs4 import BeautifulSoup
from pydantic import Field

logger = logging.getLogger("qcad-mcp")

_READ_ONLY = {"readonly": True}

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

_BLOCK_HEADERS = {"User-Agent": "qcad-mcp/0.1.0 (MCP server; +https://github.com/sandraschi/qcad-mcp)"}


async def _search_cadblocksfree(query: str, category: str, limit: int) -> list[dict]:
    """Search cadblocksfree.com for CAD blocks."""
    results = []
    url = f"https://www.cadblocksfree.com/en/search/{query.replace(' ', '-')}/" if query else "https://www.cadblocksfree.com/en/cad-blocks/"
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
                results.append({
                    "title": title[:100],
                    "source": "cadblocksfree",
                    "url": href if href.startswith("http") else f"https://www.cadblocksfree.com{href}",
                    "image_url": img if img.startswith("http") else f"https://www.cadblocksfree.com{img}" if img else "",
                    "category": cat,
                })
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
                results.append({
                    "title": title[:100],
                    "source": "biblocad",
                    "url": href if href.startswith("http") else f"https://biblocad.com{href}",
                    "image_url": img if img.startswith("http") else f"https://biblocad.com{img}" if img else "",
                    "category": category or "General",
                })
    except Exception as e:
        logger.warning("biblocad search error: %s", e)
    return results


async def _search_gallery(query: str, category: str, limit: int) -> list[dict]:
    """Return curated sample floor plans and architectural blocks."""
    samples = {
        "floor-plans": [
            {"title": "Small Apartment Floor Plan (45m\xb2)", "url": "https://www.cadblocksfree.com/en/download/small-apartment-plan.dxf", "category": "Floor Plans"},
            {"title": "Office Layout Open Plan", "url": "https://www.cadblocksfree.com/en/download/office-open-plan.dxf", "category": "Floor Plans"},
            {"title": "Two-Bedroom House Plan (80m\xb2)", "url": "https://www.cadblocksfree.com/en/download/two-bedroom-house.dxf", "category": "Floor Plans"},
            {"title": "Restaurant Floor Plan", "url": "https://www.cadblocksfree.com/en/download/restaurant-plan.dxf", "category": "Floor Plans"},
            {"title": "Classroom Layout", "url": "https://www.cadblocksfree.com/en/download/classroom.dxf", "category": "Floor Plans"},
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
        results = [item for cat_items in samples.values() for item in cat_items if query.lower() in item["title"].lower()]
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


async def plan_blocks(
    query: Annotated[str, Field(default="", description="Search query (empty = browse all in category).")] = "",
    category: Annotated[str, Field(default="", description="Category filter: furniture, doors-windows, kitchens, bathrooms, floor-plans, etc.")] = "",
    source: Annotated[str, Field(default="all", description="Source: cadblocksfree, biblocad, gallery, or all")] = "all",
    limit: Annotated[int, Field(default=20, description="Max results.")] = 20,
) -> dict:
    """Search CAD block libraries for architectural blocks, furniture, doors, and sample floor plans.

    Use plan_blocks_download to import a block directly into the local depot.

    ## Return Format
    {"success": bool, "results": list, "source": str}

    ## Examples
    await plan_blocks(query="sofa", category="furniture")
    await plan_blocks(category="floor-plans", limit=5)
    await plan_blocks(query="kitchen")
    """
    all_results = []
    sources = [source] if source != "all" else list(_BLOCK_SOURCES.keys())
    for s in sources:
        if s in _BLOCK_SOURCES:
            results = await _BLOCK_SOURCES[s](query, category, limit)
            all_results.extend(results)
    all_results.sort(key=lambda x: x.get("category", ""))
    return {"success": True, "source": source, "results": all_results[:limit]}


async def plan_blocks_download(
    title: Annotated[str, Field(description="Block title (used as filename).")],
    source: Annotated[str, Field(description="Source from search results.")],
    url: Annotated[str, Field(description="Download URL from search results.")],
) -> dict:
    """Download a CAD block from a library into the local depot.

    After download, use plan_info to inspect or plan_to_svg to preview.

    ## Return Format
    {"success": bool, "filename": str, "size_kb": float, "path": str}

    ## Examples
    await plan_blocks_download(title="Sofa Collection", source="cadblocksfree", url="https://...")
    """
    from qcad_mcp.config import DEPOT_DIR

    if not url:
        return {"success": False, "error": "No download URL provided. Browse the source website."}
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers=_BLOCK_HEADERS)
            r.raise_for_status()
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()[:60]
        filename = f"{safe}.dxf"
        path = os.path.join(DEPOT_DIR, filename)
        with open(path, "wb") as f:
            f.write(r.content)
        return {"success": True, "filename": filename, "size_kb": round(len(r.content) / 1024, 1), "path": path}
    except Exception as e:
        logger.error("Block download error: %s", e)
        return {"success": False, "error": f"Download failed: {e}"}


def register(mcp):
    mcp.tool(annotations=_READ_ONLY)(plan_blocks)
    mcp.tool()(plan_blocks_download)
