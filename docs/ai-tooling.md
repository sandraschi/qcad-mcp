# AI Tooling

## Ollama Chat (CAD Expert)

The webapp includes a chat page (`/chat`) that connects to an Ollama instance for AI-assisted CAD reasoning. The server proxies chat requests to Ollama's `/api/chat` endpoint.

**Default config:**
- URL: `http://192.168.1.11:11434`
- Model: `gemma3:1b`

**Settings page** (`/settings`) lets you change the Ollama URL and model, as well as extrusion defaults (wall height, wall thickness).

## Agentic Workflows

Since QCAD MCP is a FastMCP 3.2 server, any MCP client (Claude Desktop, Cursor, OpenCode) can chain tool calls agentically:

```
1. plan_depot()            → list available DXF files
2. plan_info("plan.dxf")   → understand the drawing structure
3. plan_to_svg("plan.dxf") → preview as SVG
4. plan_analyse("plan.dxf")→ detect rooms and calculate areas
5. plan_extrude(...)       → generate 3D STL
```

### Use Cases

- **Architectural review**: Upload DXF → analyse rooms → generate SVG report with area calculations
- **Game dev pipeline**: Floor plan → extrude walls → STL → import into Unity3D/Resonite
- **Construction estimation**: Analyse wall lengths and room areas for material takeoffs
- **Renovation planning**: Extract room dimensions, door/window positions from existing plans

## Fleet Integration

The server broadcasts SSDP discovery beacons so fleet orchestrators (meta-mcp) can auto-discover it. The generated STL files can be sent to `freecad-mcp` for further optimisation, or directly imported into game engines.

```json
POST /api/v1/control/tool
{"tool": "plan_extrude", "arguments": {"file_name": "plan.dxf", "wall_height": 3.0}}
```
