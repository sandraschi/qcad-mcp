# MCP Tools (v0.5.0 — portmanteau surface)

12 tools registered: 8 portmanteaus (each with an `op` discriminator) + 4
read-only Prefab cards. Versioned at `0.5.0`. Per-op implementations live in
`src/qcad_mcp/tools/{core,modify,annotation,qcad,script,block,agentic,bim,meta}_tools.py`;
`src/qcad_mcp/tools/portmanteau.py` is the registered surface.

Call shape (MCP or REST `/api/v1/control/tool`):

```python
await plan(op="info", file_name="floorplan.dxf")
# {"success": True, "data": {"layers": [...], "entity_counts": {...}, ...}}
```

## plan — core ezdxf (no QCAD Pro needed)

```python
await plan(op="depot")  # list depot files + metadata
await plan(op="info", file_name="floorplan.dxf")
# {"success": true, "data": {"layers": [...], "entity_counts": {"LINE": 152},
#  "bbox": {...}, "blocks": [...], "dxf_version": "AC1027"}}

await plan(op="to_svg", file_name="floorplan.dxf", svg_layers=["Walls"], background="#ffffff")
# {"success": true, "output": "floorplan.svg", ...}

await plan(op="extrude", file_name="floorplan.dxf", wall_height=3.0, wall_thickness=0.3)
# {"success": true, "output": "floorplan.stl", "data": {"vertices": N, ...}}

await plan(op="export", file_name="floorplan.dxf", format="pdf", output_name="plan.pdf")
await plan(op="analyse", file_name="floorplan.dxf")
# {"success": true, "data": {"rooms": [...], "doors_windows": [...]}}

await plan(op="create", filename="room.dxf", entities=[
    {"type": "rect", "layer": "Walls", "x": 0, "y": 0, "w": 5000, "h": 4000},
    {"type": "text", "layer": "Labels", "x": 100, "y": 100, "content": "Kitchen", "height": 250},
])

await plan(op="stack", files=[
    {"file_name": "tower_L0.dxf", "base_elevation": 0},
    {"file_name": "tower_L1.dxf", "base_elevation": 3.5},
])

await plan(op="obj", file_name="floorplan.dxf")   # textured OBJ + MTL
await plan(op="glb", file_name="floorplan.dxf")   # GLB for Resonite/game import
await plan(op="drawings", file_name="floorplan.dxf")  # elevations/section/iso/roof set
```

## plan_edit — convert + modify

```python
await plan_edit(op="convert", file_name="plan.dwg", output_name="plan.dxf")
await plan_edit(op="modify", file_name="plan.dxf", operations=[
    {"op": "layer-freeze", "layer_filter": "Furniture"},
    {"op": "delete", "type_filter": "TEXT", "layer_filter": "Draft"},
])
# ops: delete, offset, layer-set-color, layer-rename, layer-freeze/thaw,
#      layer-lock/unlock, merge-layers
```

## plan_annotate — dimensions, text, hatches, blocks, arrays, BIM data

```python
await plan_annotate(op="measure", file_name="floorplan.dxf")
await plan_annotate(op="wall_data", file_name="floorplan.dxf")  # BIM JSON for freecad-mcp
await plan_annotate(op="beam_analysis", beams=[
    {"x1": 0, "y1": 0, "x2": 4000, "y2": 0, "height": 300, "width": 200},
])
await plan_annotate(op="text", file_name="plan.dxf",
    texts=[{"text": "Kitchen", "x": 1000, "y": 2000, "height": 250}])
await plan_annotate(op="dimension", file_name="plan.dxf",
    dimensions=[{"type": "aligned", "x1": 0, "y1": 0, "x2": 5000, "y2": 0, "xd": 0, "yd": -500}])
await plan_annotate(op="block_insert", file_name="plan.dxf",
    inserts=[{"block_name": "DOOR", "x": 1000, "y": 0}])
```

## plan_bim — BIM handoff

```python
await plan_bim(op="auto_dimension", file_name="floorplan.dxf", offset=400.0)
await plan_bim(op="building_meta", file_name="tower_L0.dxf")
await plan_bim(op="to_ifc_data", file_name="floorplan.dxf")
```

## plan_pro — QCAD Pro (needs install; check qcad first)

```python
await qcad(op="status")
await plan_pro(op="exec", code="print(transientEntityCount());")
await plan_pro(op="render", file_name="floorplan.dxf", format="pdf", output_name="proof.pdf")
await plan_pro(op="script", code="/* full ECMAScript, document + di pre-bound */")
```

## plan_library — blocks + scripts

```python
await plan_library(op="blocks", query="door", category="doors-windows", limit=5)
await plan_library(op="blocks_download", title="Door", source="cadblocksfree", url="https://…")
await plan_library(op="scripts_search", query="hatch")
await plan_library(op="scripts_download", title="hatch", source="gallery", url="gallery://hatch")
```

## plan_ai — natural language + transpilation

```python
await plan_ai(op="generate", goal="L-shaped pottery workshop 12m x 9m with a darkroom")
await plan_ai(op="agentic", goal="Add a 1m door to the south wall", file_name="floorplan.dxf")
await plan_ai(op="transpile", lisp_code='(command "_.LINE" (quote (0 0)) (quote (100 0)) "")')
await plan_ai(op="sampling", goal="What wall height suits a residential plan?")
```

## qcad — server + Prefab cards

```python
await qcad(op="status")            # install/running/version
await qcad(op="help", topic="extrude")
await qcad(op="shutdown", confirm=True)
await show_depot_card()            # + show_qcad_status_card, show_beam_analysis_card,
                                   #   show_building_meta_card (rich in-chat cards)
```
