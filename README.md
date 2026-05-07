# qcad-mcp — 2D CAD MCP Server

**Status**: Pre-scaffold — architecture pending implementation.

**Vision**: DXF/DWG floor plans → SVG preview + STL extrusion → Resonite/Unity3D worlds, all through MCP tools and a fleet-standard webapp.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

| Item | Details |
|------|---------|
| **Backend** | FastMCP 3.2 (planned port 10950) |
| **Frontend** | Vite + React (planned port 10951) |
| **DXF engine** | `ezdxf` (pure Python, MIT) |
| **Optional** | QCAD Pro CLI (€50.40, Swiss-made) |
