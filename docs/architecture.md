# Architecture

## Data Pipeline

```
DXF/DWG Upload
      │
      ▼
┌──────────────────────┐
│   depot/             │  DXF files + JSON metadata sidecars
│   └── floorplan.dxf  │
│   └── floorplan.meta │  (title, author, notes, tags)
└──────────────────────┘
      │
      ├──→ plan_info      → layers, entities, bbox, blocks
      ├──→ plan_to_svg    → SVG preview (layer filterable)
      ├──→ plan_extrude   → STL mesh (walls → 3D extrusion)
      ├──→ plan_export    → SVG/PNG/PDF
      ├──→ plan_analyse   → rooms, areas, doors/windows
      ├──→ plan_create    → DXF from primitives
      └──→ plan_depot     → list depot files
```

## Component Topology

```
┌──────────────────────────────────────────────────┐
│                  MCP Client / Webapp              │
│              (Claude Desktop, Vite :10967)        │
└──────────┬───────────────────────────────────────┘
           │ SSE / REST
           ▼
┌──────────────────────────────────────────────────┐
│        FastAPI + FastMCP 3.2 (:10966)             │
│                                                    │
│  ┌──────────────────────────────────────────┐     │
│  │         Core Engine: ezdxf                │     │
│  │  - DXF/DWG parser (R12-R2023)            │     │
│  │  - Layer & block iteration                │     │
│  │  - Bounding box calculation               │     │
│  │  - SVG rendering via matplotlib           │     │
│  │  - Wall entity detection + extrusion      │     │
│  │  - Room/area/door-window analysis         │     │
│  │  - DXF creation from primitives           │     │
│  └──────────────────────────────────────────┘     │
│                                                    │
│  MCP Tools (7)          REST Endpoints (12)        │
│  ┌────────────────┐    ┌─────────────────────┐    │
│  │ plan_info       │    │ GET  /api/v1/status │    │
│  │ plan_to_svg     │    │ POST /api/v1/upload │    │
│  │ plan_extrude    │    │ GET  /api/v1/depot  │    │
│  │ plan_export     │    │ GET  /api/v1/files  │    │
│  │ plan_analyse    │    │ POST /api/v1/chat   │    │
│  │ plan_create     │    │ POST /api/v1/control│    │
│  │ plan_depot      │    │ GET  /api/v1/logs   │    │
│  └────────────────┘    └─────────────────────┘    │
└──────────────────────────────────────────────────┘
```

## Depot Storage

DXF files live in `%LOCALAPPDATA%/qcad-mcp/depot/` with JSON metadata sidecars:

```
depot/
├── floorplan.dxf
├── floorplan.meta.json     # {title, author, notes, tags, created}
├── office_layout.dxf
└── office_layout.meta.json
```

The depot REST API provides CRUD operations plus SVG preview generation.

## Extrusion Pipeline

```
DXF plan
   │
   ▼
Load via ezdxf → iterate entities → filter by wall layers
   │
   ▼
Convert LINE/LWPOLYLINE → shapely LineString → offset for wall thickness
   │
   ▼
Extrude to 3D (wall height) → triangulate → numpy-stl mesh
   │
   ▼
STL output → download or send to freecad-mcp for optimization
```

## Optional QCAD Pro CLI

When `QCAD_PRO_PATH` is set, `plan_export` can use QCAD's CLI:

```
qcad.exe -no-gui -autosave output.pdf input.dxf
```

This produces higher-quality PDF output than the ezdxf+matplotlib fallback, and adds DWG support.

## Port Layout

| Port | Service | Protocol |
|:---|:---|:---|
| **10966** | FastAPI + FastMCP SSE | HTTP, SSE |
| **10967** | Vite dev server | HTTP (proxies `/api` → 10966) |
