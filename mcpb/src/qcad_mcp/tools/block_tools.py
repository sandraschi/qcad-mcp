"""CAD block search tools - search and download architectural blocks from online libraries."""

import logging
import os
from typing import Annotated

import httpx
from pydantic import Field

from qcad_mcp.helpers import (
    _BLOCK_HEADERS,
    _BLOCK_SOURCES,
)

logger = logging.getLogger("qcad-mcp")

_README_ONLY = {"readonly": True}

_MUTATING = {}


async def plan_blocks(
    query: Annotated[str, Field(default="", description="Search query (empty = browse all in category).")] = "",
    category: Annotated[
        str,
        Field(
            default="", description="Category filter: furniture, doors-windows, kitchens, bathrooms, floor-plans, etc."
        ),
    ] = "",
    source: Annotated[
        str, Field(default="all", description="Source: cadblocksfree, biblocad, gallery, or all")
    ] = "all",
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
    mcp.tool(annotations=_README_ONLY, version="0.3.0")(plan_blocks)
    mcp.tool(annotations=_MUTATING, version="0.3.0")(plan_blocks_download)
