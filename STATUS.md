# Status — qcad-mcp

**Status**: Pre-scaffold. Architecture planned, no implementation.

**Repo**: `D:\Dev\repos\qcad-mcp`
**Ports**: Backend 10950, Frontend 10951 (planned)

## Architecture

DXF/DWG floor plans → SVG preview + STL extrusion → Resonite/Unity3D worlds.

Core engine: `ezdxf` (pure Python, MIT, free). QCAD Pro (€50.40, Swiss-made) optional for DWG + high-fidelity PDF.

See `ARCHITECTURE.md` for full design.

## Next Session

Full implementation: FastMCP server with `plan_info`, `plan_to_svg`, `plan_extrude`, fleet-standard webapp with DXF viewer.
