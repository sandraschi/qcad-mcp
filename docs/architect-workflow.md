# How an Architect Designs a House — and How This Repo Automates It

This document is the bridge between architectural practice and what `qcad-mcp`
actually does. Part 1 describes the classical 2D-CAD workflow (QCAD, AutoCAD,
AutoCAD LT — the process is the same in all three). Part 2 maps every step to
an AI/automation capability in this repo. Part 3 covers downloadable object
libraries: the blocks, symbols, and scripts that keep architects from
redrawing the same door a thousand times.

## Part 1 — How an architect designs a house in QCAD / AutoCAD

### 1. Brief and program
Everything starts off-screen: who lives here, how many rooms, budget,
plot constraints, local building code (setbacks, max height, fire egress).
The output is a **room program**: a list like "3 bedrooms, 2 baths, open
kitchen-living 40 m², garage, office". No CAD yet — but this list is exactly
what our AI floor-plan generator consumes (see Part 2).

### 2. Concept sketches and massing
Rough bubble diagrams (which room touches which), then a first massing:
footprint on the plot, storeys, roof direction. In CAD this becomes the
first rough `plan_create`-equivalent: outer rectangle, a few dividing lines.
Nothing is dimensioned yet; walls are single lines, not double-line
constructions.

### 3. Floor plans, one per storey (the core deliverable)
Each floor plan is drawn at 1:50 (planning) or 1:100 (overview) with:

- **Layers as the organizing principle.** Professional template: `Walls`,
  `Doors`, `Windows`, `Text`/`Labels`, `Dimensions`, `Furniture`, `Hatch`,
  `Electrical`, `Plumbing`. Everything this repo generates follows the same
  convention (`Walls`, `Text`, …), which is why extrusion and BIM export can
  find the walls later.
- **Walls as double lines** (cavity/masonry shown true to thickness), doors as
  openings with swing arcs, windows as breaks in the wall with sill lines.
- **Blocks for repeated objects** (Part 3): doors, windows, WC, bathtub,
  kitchen units, beds, tables, cars for the garage. Insert, don't redraw.
- **Dimensions**: overall outer dimensions plus chain dimensions between
  openings. Drawn last, on their own layer, never as loose text.
- **Room labels + areas**: room name and m² in each space — the equivalent
  of our `plan_wall_data` / `plan_building_meta` room analysis.

### 4. Elevations — front, rear, left, right
Flat, scaled exterior views: facade composition, window rhythms, floor
heights, roof shape, materials/notes. Derived from the plan + chosen
floor-to-floor heights, not drawn from scratch.

### 5. Sections — the vertical cut
One or two cuts through stairs, bathrooms, roof. Shows what plans hide:
foundations, floor build-ups, roof construction, headroom. Together with
elevations, sections are what the building authority actually checks.

### 6. Roof plan, site plan, interior elevations
Roof geometry and drainage; the building placed on its plot (setbacks,
access, north arrow); flat views of kitchen/bathroom walls with tiling
and fixtures.

### 7. Details and schedules (1:5–1:20)
Wall/foundation/roof build-ups, window installation details, door schedule
(every door numbered, sized, specified), room finish schedule.

### 8. Coordination, permits, construction
Plans → structural engineer, MEP, energy calculations → permit set →
construction drawings with revision clouds. The CAD file is a living
document through all of it, which is why **modify-in-place**
(`plan_modify`) matters more than generate-once.

The pattern to notice: the architect draws the **floor plan once**, then
derives everything else from it, and reuses library objects everywhere.
That is precisely the automation shape in Part 2.

## Part 2 — Automating it with AI (what this repo does today)

| Architect step | Repo capability | Where | Status |
|---|---|---|---|
| Room program → first plan | Natural-language floor plan generator (rooms, sizes, presets: office, studio, villa, church…) | Demo page, `plan_agentic` + `plan_create` | Working |
| Layer setup | Automatic `Walls`/`Text`/… layers on every generated plan | `plan_create` | Working |
| Room labels + areas | Room detection, areas, dimensions report | `plan_wall_data`, `plan_building_meta`, Analyse page | Working |
| Dimensioning | Automatic exterior + opening dimensions | `plan_auto_dimension`, `plan_dimension` | Working (QCAD Pro for some paths) |
| Modify / revise | Move/resize/delete entities, merge layers | `plan_modify`, Depot page | Working |
| 2D preview | SVG preview with layer filter + dark/light background | `plan_to_svg`, Viewer/Depot pages | Working |
| 3D massing from plan | Wall extrusion to STL (Three.js in-browser preview) | `plan_extrude`, Extrusion page, Models page | Working |
| Solid 3D object | STL → B-Rep solid via FreeCAD (`/api/v1/freecad/solid`) | Extrusion page → freecad-mcp `mesh_to_solid` | Working (FreeCAD + backend required) |
| BIM data | Wall/opening schema JSON for IFC pipelines | `plan_to_ifc_data` | Working |
| Elevations / sections / iso | Projected views from the 3D model (TechDraw) | Planned via freecad-mcp | Roadmap |
| Schedules | Door/window/finish tables from block + layer data | Roadmap | Roadmap |

Two honest boundaries: the AI generates **geometry**, not code compliance —
setbacks, egress widths, structural spans still need an architect's sign-off.
And QCAD Pro (paid, cheap) unlocks the DWG/PDF/render paths that the free
engine covers via ezdxf/matplotlib instead.

## Part 3 — Downloadable object libraries (never draw a door twice)

Architects work from libraries, and so does this repo. Three library
systems, all landing in the local **depot** (`%LOCALAPPDATA%\qcad-mcp\depot`):

### CAD blocks — doors, windows, furniture, fixtures
- `plan_blocks` — search by keyword + category (furniture, doors-windows,
  kitchens, bathrooms, floor-plans). Live source: **cadblocksfree.com**,
  with curated built-in results as fallback when offline.
- `plan_blocks_download` — downloads a block straight into the depot
  (Blocks page, one click).
- Insert blocks into plans with `plan_block_insert`; query what's inside
  with `plan_blocks` on the depot side.

### QCAD automation scripts
- `plan_scripts_search` / `plan_scripts_download` — sources: built-in
  **gallery** (door swings, dimension helpers, layer tools, room areas…),
  QCAD **examples**, and GitHub **gists**. Scripts page in the webapp.
- Run them headlessly with `plan_script` (QCAD Pro present) or
  `plan_exec`.

### Reference floor plans
`docs/floorplan-sources.md` catalogs free/paid/historic plan sources
(Wikimedia public-domain palaces and churches, cadblocksfree DXF plans,
parametric generators). Nothing beats tracing a good plan while learning —
and the Demo page presets (Versailles, baroque church, Palladio-style
villa) are themselves study objects: generate one, read its layers,
modify it.

### Practical library workflow
1. Generate the shell: Demo page → room program → DXF in depot.
2. Furnish it: Blocks page → search "bed"/"sofa"/"WC" → download →
   `plan_block_insert` at the right coordinates.
3. Dimension it: `plan_auto_dimension` → check on Viewer page.
4. Go 3D: Extrusion page → STL → Three.js check → FreeCAD solid.
5. Export: `plan_export` → PDF for the client, DXF/DWG for the engineer.

## The goal: architect-in-a-repo

One room program in, one coordinated drawing set out — plans, elevations,
sections, 3D, schedules — with library objects filling the repetitive 80%
and the architect spending judgment on the 20% that matters. The floor-plan
half of that pipeline works today; elevations and schedules are next.
