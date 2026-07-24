# Floorplan Sources — Free, Paid & Historic

## Free Sources

| Source | Format | Quality | Notes |
|--------|--------|---------|-------|
| [Wikimedia Commons Floor Plans](https://commons.wikimedia.org/wiki/Category:Floor_plans) | PNG/SVG | Variable | Public domain historic buildings, churches, palaces. Versailles, Hagia Sophia, Palladio villas. |
| [OpenHouse.ai](https://openhouse.ai) | Web viewer | Good | Parametric generation from constraints (rooms, size, style). No DXF export. |
| [GitHub: floorplan-generator](https://github.com/search?q=floorplan+generator&type=repositories) | Python/SVG | Developer | Parametric scripts (OpenSCAD, FreeCAD, Python+ezdxf). Source code you run. |
| [GitHub: house-plan-generator](https://github.com/search?q=house+plan+generator&type=repositories) | SCAD/FCStd | Developer | Mostly FreeCAD/OpenSCAD macros. Generates 3D models with plan views. |
| [ArchiWeb](https://www.archiweb.cz) | Images | Professional | Czech/Slovak architecture database. Many plans as images. |
| [ArchDaily Projects](https://www.archdaily.com/search/projects) | Images | Professional | Built projects with floorplan images. Not downloadable as DXF. |
| [Floorplanner.com](https://www.floorplanner.com) | Proprietary | Good | Free tier with basic features. Export as image only. |
| [HomeByMe](https://home.by.me) | Proprietary | Good | Free 3D planner, export as image. |

## Paid Marketplaces

| Source | Price | Format | Notes |
|--------|-------|--------|-------|
| [ArchitecturalDesigns.com](https://www.architecturaldesigns.com) | $1,000-$2,000 | PDF | Professionally designed, build-ready plans. No DXF. |
| [HousePlans.com](https://www.houseplans.com) | $800-$1,500 | PDF | Large catalog, searchable by style/bedrooms. |
| [Etsy — "floor plan bundle"](https://www.etsy.com/search?q=floor+plan+bundle) | $5-$50 | PDF/Image | Amateur and vintage reprints. Cheap but unreliable. |
| [Plans.com](https://www.plans.com) | $600-$2,000 | PDF | Formerly HomePlans.com. Large catalog. |
| [The House Plan Shop](https://www.houseplanshop.com) | $500-$1,500 | PDF | Focus on cottage/cabin/traditional. |
| [CADBlocksFree](https://www.cadblocksfree.com) | Free | DWG/DXF | Individual CAD blocks, not full floorplans. |

## Historic / Public Domain

Wikimedia Commons has thousands of historic floorplans — palaces, cathedrals, fortresses — published as line drawings in the public domain. Notable ones:

| Building | Era | Why interesting |
|----------|-----|----------------|
| **Palace of Versailles** | 17th c. | 700-room baroque palace. Central axis, king's wing, Hall of Mirrors. |
| **Hagia Sophia** | 6th c. | Central dome 31m, semi-domes, buttresses. Monumental religious architecture. |
| **Palladio's Villas** (La Rotonda, Barbaro, etc.) | 16th c. | Symmetrical Renaissance perfection. Modular room layouts. |
| **Alhambra** | 13th-14th c. | Nasrid palace complex. Courtyard-centric, intricate geometry. |
| **Taj Mahal** | 17th c. | Symmetrical Mughal garden tomb with domed central hall. |
| **Gothic cathedrals** (Notre Dame, Reims, Amiens) | 12th-14th c. | Cruciform plan, nave/aisles/transept/apse, radiating chapels. |

These are ideal candidates for the raster → DXF pipeline: scan the Wikimedia line drawing, trace with potrace/inkscape-mcp, clean with plan_modify.

## Raster → DXF Pipeline

Scanned floorplan → DXF in 3 steps:

```
Scan at 300-600 DPI
       ↓
Vectorize: inkscape-mcp trace_bitmap() or potrace
       ↓
Convert SVG → DXF (ezdxf or Inkscape export)
       ↓
Clean: qcad-mcp plan_modify (merge, re-layer, re-dimension)
```

The vectorized result is noisy — text is garbled, lines have gaps, dimensions are rough. But the wall geometry is usable after cleanup. For a scanned Versailles plan, you'd get the basic room layout within minutes, then spend an hour cleaning up layers and re-annotating rooms.

## Generate Parametrically (No Scan Needed)

For historic buildings where the floorplan is known (Wikimedia line drawing, academic paper), it's often faster to build parametrically in qcad-mcp's Demo page:

1. Trace the Wikimedia image as reference in QCAD
2. Measure room proportions from the image (e.g. Versailles: 400m width, 300m depth)
3. Describe in the Demo page: *"Versailles-style palace..."*
4. The parametric fallback generates a symmetrical room grid you can then refine

The baroque church preset (45m nave, apse, transept, columns) already demonstrates this approach — it's a Versailles chapel scaled down. A full Versailles preset would add the central axis, Hall of Mirrors, king's/queen's wings, and gardens.
