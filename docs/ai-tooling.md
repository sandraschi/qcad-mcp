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
1. qcad_status()             → check QCAD Pro availability
2. plan_depot()              → list available DXF files
3. plan_info("plan.dxf")     → understand the drawing structure
4. plan_to_svg("plan.dxf")   → preview as SVG
5. plan_analyse("plan.dxf")  → detect rooms and calculate areas
6. plan_script(code, ...)    → execute custom ECMAScript
7. plan_render("plan.dxf")   → export native PDF/SVG
```

### ECMAScript Bridge: The LLM Is the Library

Unlike AutoCAD's AutoLISP ecosystem — 40 years of shared forum routines for wall area calculators, beam schedules, and layer management — QCAD Pro has no comparable script library. It doesn't need one.

**The AI is the library.** `plan_script` and `plan_agentic` let an LLM generate ECMAScript on-demand from first principles:

```
User: "Label every closed polyline with its area in m²"

AI generates:
  var ents = document.queryAllEntities();
  for (var i = 0; i < ents.length; i++) {
      var e = document.queryEntity(ents[i]);
      if (e instanceof RPolylineEntity && e.getData().isClosed()) {
          // calculate area, add text label...
      }
  }

→ plan_script(code=..., file_name="floorplan.dxf") → executed
```

No hunting for a pre-written LISP routine on a 20-year-old forum thread. The AI writes fresh, correct ECMAScript for each task — tailored to the specific drawing and goal.

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
