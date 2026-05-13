"""ECMAScript script library tools — search and download QCAD ECMAScript scripts."""

import logging
import os
from typing import Annotated

import httpx
from bs4 import BeautifulSoup
from pydantic import Field

logger = logging.getLogger("qcad-mcp")

_SCRIPT_SOURCES: dict = {}
_SCRIPT_CATEGORIES = ["drawing", "modify", "dimension", "export", "utility", "block", "layer", "geometry"]


def _script_source(name: str):
    """Decorator to register a script search source."""
    def deco(fn):
        _SCRIPT_SOURCES[name] = fn
        return fn
    return deco


@_script_source("gallery")
async def _search_script_gallery(query: str, category: str, limit: int) -> list[dict]:
    """Curated local gallery of QCAD ECMAScript scripts."""
    gallery = [
        {"title": "Rectangle Generator", "category": "drawing",
         "description": "Generate a rectangle from width/height parameters. Useful as a floor plan starting point.",
         "source": "gallery", "url": "gallery://rectangle.js"},
        {"title": "Door Swing Arc", "category": "drawing",
         "description": "Draw a door swing arc (90°) at a given hinge point, wall angle, and door width.",
         "source": "gallery", "url": "gallery://door_swing.js"},
        {"title": "Auto-Dimension Polyline", "category": "dimension",
         "description": "Add aligned dimensions to all segments of a selected polyline automatically.",
         "source": "gallery", "url": "gallery://dim_polyline.js"},
        {"title": "Layer Report", "category": "utility",
         "description": "Generate a text report of all layers with entity counts, colors, and frozen/locked state.",
         "source": "gallery", "url": "gallery://layer_report.js"},
        {"title": "Room Area Labels", "category": "geometry",
         "description": "Find all closed polylines and add text labels showing the enclosed area in m².",
         "source": "gallery", "url": "gallery://room_areas.js"},
        {"title": "Batch DXF to SVG", "category": "export",
         "description": "Export all DXF files in a directory to SVG using QCAD Pro rendering.",
         "source": "gallery", "url": "gallery://batch_svg.js"},
        {"title": "Merge Layers", "category": "layer",
         "description": "Merge all entities from a source layer into a target layer, then delete the source.",
         "source": "gallery", "url": "gallery://merge_layers.js"},
        {"title": "Grid Generator", "category": "drawing",
         "description": "Generate an orthogonal grid of lines with specified spacing and extent.",
         "source": "gallery", "url": "gallery://grid.js"},
        {"title": "Entity Counter", "category": "utility",
         "description": "Count entities by type and layer, output as a structured report.",
         "source": "gallery", "url": "gallery://entity_count.js"},
        {"title": "Wall Centerline", "category": "geometry",
         "description": "Extract the centerline from parallel wall polylines (offset half the wall thickness).",
         "source": "gallery", "url": "gallery://wall_centerline.js"},
        {"title": "Scale Drawing", "category": "modify",
         "description": "Scale all entities in the drawing by a given factor around the origin.",
         "source": "gallery", "url": "gallery://scale.js"},
        {"title": "Rotate Selection", "category": "modify",
         "description": "Rotate all entities by a given angle around a center point.",
         "source": "gallery", "url": "gallery://rotate.js"},
    ]
    results = []
    ql = query.lower() if query else ""
    for item in gallery:
        if ql and ql not in item["title"].lower() and ql not in item["description"].lower():
            continue
        if category and category != item.get("category", ""):
            continue
        results.append(item)
    return results[:limit]


@_script_source("gist")
async def _search_script_gist(query: str, category: str, limit: int) -> list[dict]:
    """Search GitHub Gist for QCAD ECMAScript scripts."""
    try:
        q = query or "qcad script"
        url = f"https://gist.github.com/search?q={httpx.QueryParam(q)}&ref=simplesearch"
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers={"Accept": "text/html"})
            soup = BeautifulSoup(r.text, "html.parser")
            results = []
            for item in soup.select(".gist-snippet")[:limit]:
                title_el = item.select_one(".gist-snippet-title a")
                desc_el = item.select_one(".gist-snippet-description")
                link_el = item.select_one("a[href*='/']")
                title = title_el.get_text(strip=True) if title_el else "QCAD Script"
                desc = desc_el.get_text(strip=True) if desc_el else ""
                link = "https://gist.github.com" + link_el["href"] if link_el and link_el.get("href") else ""
                results.append({
                    "title": title, "description": desc, "url": link,
                    "source": "gist", "category": category or "utility",
                })
            return results
    except Exception:
        return []


@_script_source("examples")
async def _search_script_examples(query: str, category: str, limit: int) -> list[dict]:
    """Index QCAD Pro bundled example scripts."""
    qcad_examples = [
        {"title": "ExMinimal — Hello World", "category": "utility",
         "description": "Minimal QCAD script: shows a Hello World message. Best starting point for learning.",
         "source": "examples", "path": "scripts/Misc/Examples/ExMinimal/ExMinimal.js"},
        {"title": "Draw Examples — Lines, Circles, Arcs", "category": "drawing",
         "description": "Examples of creating all basic entity types programmatically.",
         "source": "examples", "path": "scripts/Misc/Examples/DrawExamples/DrawExamples.js"},
        {"title": "Modify Examples — Move, Rotate, Scale", "category": "modify",
         "description": "Examples of entity modification operations.",
         "source": "examples", "path": "scripts/Misc/Examples/ModifyExamples/ModifyExamples.js"},
        {"title": "IO Examples — Import/Export", "category": "export",
         "description": "Examples of file import and export operations in QCAD.",
         "source": "examples", "path": "scripts/Misc/Examples/IOExamples/IOExamples.js"},
        {"title": "Layer Examples", "category": "layer",
         "description": "Examples of layer creation, modification, and management.",
         "source": "examples", "path": "scripts/Misc/Examples/LayerExamples/LayerExamples.js"},
        {"title": "Block Examples", "category": "block",
         "description": "Examples of block creation and insertion.",
         "source": "examples", "path": "scripts/Misc/Examples/BlockExamples/BlockExamples.js"},
        {"title": "Math Examples — Vectors, Trig", "category": "geometry",
         "description": "Examples of RVector, RMath, and geometric calculations.",
         "source": "examples", "path": "scripts/Misc/Examples/MathExamples/MathExamples.js"},
        {"title": "Command Line Examples", "category": "utility",
         "description": "Examples of headless/CLI script patterns for batch processing.",
         "source": "examples", "path": "scripts/Misc/Examples/CommandLineExamples/CommandLineExamples.js"},
    ]
    results = []
    ql = query.lower() if query else ""
    for item in qcad_examples:
        if ql and ql not in item["title"].lower() and ql not in item["description"].lower():
            continue
        if category and category != item.get("category", ""):
            continue
        results.append(item)
    return results[:limit]


def _get_gallery_script(script_id: str) -> str:
    """Return the content of a curated gallery script."""
    scripts = {
        "rectangle.js": """// Rectangle Generator — creates a rectangle from width/height
qApp.applicationName = "RectangleGenerator";
var storage = new RMemoryStorage();
var spatialIndex = new RSpatialIndexSimple();
var document = new RDocument(storage, spatialIndex);
var di = new RDocumentInterface(document);

var op = new RAddObjectsOperation();
var w = 100; var h = 80;  // default dimensions
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,0), new RVector(w,0))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(w,0), new RVector(w,h))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(w,h), new RVector(0,h))));
op.addObject(new RLineEntity(document, new RLineData(new RVector(0,h), new RVector(0,0))));
op.apply(document);

di.exportFile("rectangle_output.dxf", "DXF 2018");
""",
        "door_swing.js": """// Door Swing Arc — draws a 90° door arc at a hinge point
var hingeX = 0; var hingeY = 0;     // hinge position
var doorWidth = 900;                  // door width in mm
var wallAngleDeg = 0;                 // wall angle in degrees

var wallAngle = wallAngleDeg * Math.PI / 180;
var op = new RAddObjectsOperation();

// Door line from hinge to open position
var openAngle = wallAngle + Math.PI / 2;
op.addObject(new RLineEntity(document,
    new RLineData(new RVector(hingeX, hingeY),
                   new RVector(hingeX + doorWidth * Math.cos(openAngle),
                                hingeY + doorWidth * Math.sin(openAngle)))));

// Swing arc
op.addObject(new RArcEntity(document,
    new RArcData(new RVector(hingeX, hingeY), doorWidth,
                  wallAngle, wallAngle + Math.PI / 2, false)));

op.apply(document);
""",
        "dim_polyline.js": """// Auto-Dimension Polyline — adds aligned dims to each polyline segment
var ents = document.queryAllEntities();
var op = new RAddObjectsOperation();

for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e || !(e instanceof RPolylineEntity)) continue;

    var vertices = e.getData().getVertices();
    for (var j = 0; j < vertices.length - 1; j++) {
        var p1 = vertices[j];
        var p2 = vertices[j + 1];
        var midX = (p1.getX() + p2.getX()) / 2;
        var midY = (p1.getY() + p2.getY()) / 2;
        var dx = p2.getX() - p1.getX();
        var dy = p2.getY() - p1.getY();
        var len = Math.sqrt(dx*dx + dy*dy);
        // Offset dimension line perpendicular to segment
        var perpX = -dy / len;
        var perpY = dx / len;
        var offset = 50;
        var dimX = midX + perpX * offset;
        var dimY = midY + perpY * offset;
        op.addObject(new RDimAlignedEntity(document,
            new RDimAlignedData(p1, p2, new RVector(dimX, dimY))));
    }
}
op.apply(document);
""",
        "layer_report.js": R"""// Layer Report — generates a text report of all layers
var layerIds = document.queryAllLayers();
var report = "Layer Report\n" + "=".repeat(40) + "\n";

for (var i = 0; i < layerIds.length; i++) {
    var layer = document.queryLayer(layerIds[i]);
    if (!layer) continue;
    var ents = document.queryAllEntities();
    var count = 0;
    for (var j = 0; j < ents.length; j++) {
        var e = document.queryEntity(ents[j]);
        if (e && e.getLayerId && e.getLayerId().toString() === layerIds[i].toString()) {
            count++;
        }
    }
    report += "Layer: " + layer.getName() +
              " | Color: " + layer.getColor().name() +
              " | Frozen: " + layer.isFrozen() +
              " | Locked: " + layer.isLocked() +
              " | Entities: " + count + "\n";
}
print("__QCAD_MCP_MEASURE__");
// Return report as structured data
var lines = report.split("\n");
var result = {report_lines: lines};
print(JSON.stringify(result));
""",
        "room_areas.js": """// Room Area Labels — find closed polylines and label with m² area
var ents = document.queryAllEntities();
var op = new RAddObjectsOperation();

for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e || !(e instanceof RPolylineEntity)) continue;

    var vertices = e.getData().getVertices();
    if (vertices.length < 3) continue;

    // Check if closed
    var last = vertices[vertices.length - 1];
    var first = vertices[0];
    var isClosed = Math.abs(first.getX() - last.getX()) < 0.001
                && Math.abs(first.getY() - last.getY()) < 0.001;
    if (!isClosed) continue;

    // Shoelace formula for area
    var area = 0;
    for (var j = 0; j < vertices.length; j++) {
        var v1 = vertices[j];
        var v2 = vertices[(j + 1) % vertices.length];
        area += (v1.getX() * v2.getY()) - (v2.getX() * v1.getY());
    }
    area = Math.abs(area) / 2;
    var areaM2 = area / 1000000;  // mm² → m²

    // Find centroid for label position
    var cx = 0; var cy = 0;
    for (var k = 0; k < vertices.length; k++) {
        cx += vertices[k].getX();
        cy += vertices[k].getY();
    }
    cx /= vertices.length;
    cy /= vertices.length;

    op.addObject(new RTextEntity(document,
        new RTextData(new RVector(cx, cy), 200, 0,
            areaM2.toFixed(2) + " m²",
            "Standard", RS.HAlignCenter, RS.VAlignMiddle,
            RS.UnknownUnit, 0, 0, 0, false, false, 0, false, false)));
}
op.apply(document);
""",
        "batch_svg.js": """// Batch DXF to SVG — export all DXF files in a directory to SVG
// NOTE: This is a template — adjust paths for your environment.

var inputDir = "C:/Users/Public/Documents/QCAD/";
var outputDir = "C:/Users/Public/Documents/QCAD/svg_output/";

// QCAD file system access
var dir = new QDir(inputDir);
var filters = ["*.dxf"];
var files = dir.entryList(filters, QDir.Files, QDir.Name);

for (var i = 0; i < files.length; i++) {
    var inFile = inputDir + files[i];
    var outFile = outputDir + files[i].replace(".dxf", ".svg");

    var storage = new RMemoryStorage();
    var spatialIndex = new RSpatialIndexSimple();
    var doc = new RDocument(storage, spatialIndex);
    var di = new RDocumentInterface(doc);
    di.importFile(inFile);

    // The SVG export is handled by QCAD Pro CLI tools externally
    print("Processed: " + files[i] + " (" + doc.queryAllEntities().length + " entities)");
}

print("Batch complete: " + files.length + " files processed.");
""",
        "merge_layers.js": """// Merge Layers — move all entities from source to target layer
var sourceLayer = "OldLayer";   // change this
var targetLayer = "0";          // change this

var srcId = null; var tgtId = null;
var layerIds = document.queryAllLayers();
for (var i = 0; i < layerIds.length; i++) {
    var layer = document.queryLayer(layerIds[i]);
    if (!layer) continue;
    if (layer.getName() === sourceLayer) srcId = layerIds[i];
    if (layer.getName() === targetLayer) tgtId = layerIds[i];
}

if (!srcId || !tgtId) {
    print("Source or target layer not found.");
} else {
    var ents = document.queryAllEntities();
    var op = new RModifyObjectsOperation();
    var count = 0;
    for (var i = 0; i < ents.length; i++) {
        var e = document.queryEntity(ents[i]);
        if (e && e.getLayerId() && e.getLayerId().toString() === srcId.toString()) {
            e.setLayerId(tgtId);
            op.addObject(e);
            count++;
        }
    }
    op.apply(document);
    print("Merged " + count + " entities from '" + sourceLayer + "' to '" + targetLayer + "'");
}
""",
        "grid.js": """// Grid Generator — create an orthogonal grid of lines
var spacingX = 1000;   // mm
var spacingY = 1000;
var extentX = 10000;
var extentY = 8000;

var op = new RAddObjectsOperation();

// Vertical lines
for (var x = 0; x <= extentX; x += spacingX) {
    op.addObject(new RLineEntity(document,
        new RLineData(new RVector(x, 0), new RVector(x, extentY))));
}

// Horizontal lines
for (var y = 0; y <= extentY; y += spacingY) {
    op.addObject(new RLineEntity(document,
        new RLineData(new RVector(0, y), new RVector(extentX, y))));
}

op.apply(document);
print("Grid generated: " + ((extentX/spacingX + 1) + (extentY/spacingY + 1)) + " lines");
""",
        "entity_count.js": R"""// Entity Counter — count entities by type and layer
var ents = document.queryAllEntities();
var byType = {};
var byLayer = {};

for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e) continue;
    var t = "unknown";
    if (e instanceof RLineEntity) t = "line";
    else if (e instanceof RCircleEntity) t = "circle";
    else if (e instanceof RArcEntity) t = "arc";
    else if (e instanceof RPolylineEntity) t = "polyline";
    else if (e instanceof RSplineEntity) t = "spline";
    else if (e instanceof RTextEntity) t = "text";
    else if (e instanceof RDimEntity) t = "dimension";
    else if (e instanceof RHatchEntity) t = "hatch";
    else if (e instanceof RBlockRefEntity) t = "block_ref";
    byType[t] = (byType[t] || 0) + 1;

    var lid = e.getLayerId ? e.getLayerId().toString() : "?";
    var layer = document.queryLayer(e.getLayerId());
    var lname = layer ? layer.getName() : lid;
    if (!byLayer[lname]) byLayer[lname] = {};
    byLayer[lname][t] = (byLayer[lname][t] || 0) + 1;
}

print("__QCAD_MCP_MEASURE__");
print(JSON.stringify({by_type: byType, by_layer: byLayer, total: ents.length}));
""",
        "wall_centerline.js": """// Wall Centerline — extract centerline from parallel wall lines
// Finds pairs of parallel lines within wall thickness distance and draws the centerline

var wallThickness = 300;  // mm
var tolerance = 10;       // mm

var ents = document.queryAllEntities();
var lines = [];
for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (e instanceof RLineEntity) {
        var d = e.getData();
        lines.push({
            entity: e,
            x1: d.getStartPoint().getX(), y1: d.getStartPoint().getY(),
            x2: d.getEndPoint().getX(),   y2: d.getEndPoint().getY(),
            dx: d.getEndPoint().getX() - d.getStartPoint().getX(),
            dy: d.getEndPoint().getY() - d.getStartPoint().getY()
        });
    }
}

var op = new RAddObjectsOperation();
var centerlineLayer = new RLayer(document, "Centerlines", false, false, new RColor("magenta"));
op.addObject(centerlineLayer);

// Find parallel pairs and draw centerlines
for (var i = 0; i < lines.length; i++) {
    for (var j = i + 1; j < lines.length; j++) {
        var a = lines[i]; var b = lines[j];
        // Check if roughly parallel (dot product near ±1)
        var lenA = Math.sqrt(a.dx*a.dx + a.dy*a.dy);
        var lenB = Math.sqrt(b.dx*b.dx + b.dy*b.dy);
        if (lenA < 1 || lenB < 1) continue;
        var dot = (a.dx*b.dx + a.dy*b.dy) / (lenA * lenB);
        if (Math.abs(dot) < 0.99) continue;

        // Check distance is within wall thickness
        var midAX = (a.x1 + a.x2) / 2; var midAY = (a.y1 + a.y2) / 2;
        var midBX = (b.x1 + b.x2) / 2; var midBY = (b.y1 + b.y2) / 2;
        var dist = Math.sqrt((midBX-midAX)*(midBX-midAX) + (midBY-midAY)*(midBY-midAY));
        if (Math.abs(dist - wallThickness) > tolerance) continue;

        // Draw centerline between midpoints
        op.addObject(new RLineEntity(document,
            new RLineData(new RVector(midAX, midAY), new RVector(midBX, midBY))));
    }
}
op.apply(document);
""",
        "scale.js": """// Scale Drawing — scale all entities by a given factor
var scaleFactor = 2.0;  // change this

var ents = document.queryAllEntities();
var op = new RModifyObjectsOperation();

for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e) continue;
    e.scale(scaleFactor, new RVector(0, 0));
    op.addObject(e);
}
op.apply(document);
print("Scaled " + ents.length + " entities by factor " + scaleFactor);
""",
        "rotate.js": """// Rotate Selection — rotate all entities by a given angle
var angleDeg = 45;           // degrees
var centerX = 0; var centerY = 0;  // rotation center

var angleRad = angleDeg * Math.PI / 180;
var center = new RVector(centerX, centerY);

var ents = document.queryAllEntities();
var op = new RModifyObjectsOperation();

for (var i = 0; i < ents.length; i++) {
    var e = document.queryEntity(ents[i]);
    if (!e) continue;
    e.rotate(angleRad, center);
    op.addObject(e);
}
op.apply(document);
print("Rotated " + ents.length + " entities by " + angleDeg + "°");
""",
    }
    return scripts.get(script_id, "")


def register(mcp):
    from qcad_mcp.config import DEPOT_DIR

    _READ_ONLY = {"readonly": True}

    @mcp.tool(annotations=_READ_ONLY)
    async def plan_scripts_search(
        query: Annotated[str, Field(default="", description="Search term for script title or description.")] = "",
        category: Annotated[str, Field(default="", description="Filter by category: drawing, modify, dimension, export, utility, block, layer, geometry.")] = "",
        source: Annotated[str, Field(default="all", description="Source: gallery, gist, examples, or all.")] = "all",
        limit: Annotated[int, Field(default=20, description="Max results.")] = 20,
    ) -> dict:
        """Search QCAD ECMAScript libraries for reusable CAD scripts.

        Searches curated gallery, GitHub Gist, and QCAD bundled examples.

        ## Return Format
        {"success": bool, "source": str, "results": [{"title": str, "description": str, "source": str, "url": str, ...}]}

        ## Examples
        await plan_scripts_search(query="dimension")
        await plan_scripts_search(category="drawing", source="gallery")
        """
        all_results = []
        sources = [source] if source != "all" else list(_SCRIPT_SOURCES.keys())
        for s in sources:
            if s in _SCRIPT_SOURCES:
                try:
                    results = await _SCRIPT_SOURCES[s](query, category, limit)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning("Script source %s error: %s", s, e)
        all_results.sort(key=lambda x: x.get("title", ""))
        return {"success": True, "source": source, "results": all_results[:limit]}

    @mcp.tool()
    async def plan_scripts_download(
        title: Annotated[str, Field(description="Script title, used as filename.")],
        source: Annotated[str, Field(description="Source from search results.")],
        url: Annotated[str, Field(default="", description="Download URL or gallery://id for local scripts.")] = "",
    ) -> dict:
        """Download an ECMAScript from a library to the local depot.

        Gallery scripts (gallery://id) are pre-curated and served from the local bundle.
        Downloaded .js files go to the depot and can be viewed, edited, or
        used with plan_script.

        ## Return Format
        {"success": bool, "filename": str, "size_kb": float, "content": str}

        ## Examples
        await plan_scripts_download(title="Door Swing Arc", source="gallery", url="gallery://door_swing.js")
        """
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()[:60]
        filename = f"{safe}.js" if not safe.endswith(".js") else safe
        path = os.path.join(DEPOT_DIR, filename)

        if url.startswith("gallery://"):
            script_id = url.replace("gallery://", "")
            content = _get_gallery_script(script_id)
            if content:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                size_kb = round(len(content.encode("utf-8")) / 1024, 1)
                return {"success": True, "filename": filename, "size_kb": size_kb, "path": path,
                        "content": content[:500] + ("..." if len(content) > 500 else "")}
            return {"success": False, "error": f"Gallery script not found: {script_id}"}

        if url:
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    r = await client.get(url)
                    r.raise_for_status()
                content = r.text
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "filename": filename, "size_kb": round(len(content.encode("utf-8")) / 1024, 1),
                        "path": path, "content": content[:500] + ("..." if len(content) > 500 else "")}
            except Exception as e:
                logger.error("Script download error: %s", e)
                return {"success": False, "error": f"Download failed: {e}"}
        return {"success": False, "error": "No URL or gallery reference provided."}
