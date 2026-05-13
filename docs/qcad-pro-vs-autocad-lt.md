# QCAD Pro vs. AutoCAD LT

For MCP tooling and AI-driven CAD automation, the choice of CAD engine matters. Here's how QCAD Pro and AutoCAD LT compare.

## At a Glance

| | QCAD Pro | AutoCAD LT |
|---|---|---|
| **Vendor** | RibbonSoft (Switzerland) | Autodesk (USA) |
| **First release** | 1999 | 1993 |
| **Pricing** | ~€42 one-time | ~€550/year subscription |
| **Platform** | Windows, macOS, Linux | Windows, macOS |
| **License** | Proprietary (Community Edition is GPLv2) | Proprietary |
| **File format** | DXF R12–R2023, DWG (read/write via Teigha) | DWG (native), DXF |
| **Scripting** | ECMAScript (QtScript) — full API | AutoLISP, .NET, VBA, JavaScript |

## 2D Drafting Capabilities

Both are professional 2D CAD applications. The core drafting feature set is comparable:

| Feature | QCAD Pro | AutoCAD LT |
|---|---|---|
| Layers, blocks, xrefs | Full | Full |
| Dimensions (aligned, radial, angular, ordinate) | Full | Full |
| Hatches (ANSI, ISO, custom patterns) | Full | Full |
| Text / MTEXT | Full | Full |
| Polylines, splines, arcs, circles | Full | Full |
| Paper space / layouts / viewports | Full | Full |
| PDF/DWG/DXF import & export | Full | Full |
| Command line interface | Full | Full |
| Parametric constraints | Partial | Full |
| Dynamic blocks | No | Yes |
| 3D modeling | None (2D only) | None (2D only) |

**Bottom line**: For architectural floor plans, mechanical drafting, and general 2D CAD work, QCAD Pro matches AutoCAD LT on core features. AutoCAD LT pulls ahead on parametric constraints and dynamic blocks — features mostly relevant for mechanical/manufacturing.

## Scripting & Automation (the big differentiator for MCP)

This is where the comparison gets interesting for AI tooling.

### QCAD Pro — ECMAScript (QtScript)

```javascript
// Add entities programmatically
var op = new RAddObjectsOperation();
op.addObject(new RLineEntity(document,
    new RLineData(new RVector(0,0), new RVector(100,0))));
op.apply(document);

// Modify layers
var layerOp = new RModifyObjectsOperation();
layerOp.addObject(new RLayer(document, "Walls", false, false,
    new RColor("red")));
layerOp.apply(document);

// Export
di.exportFile("output.dxf", "DXF 2018");
```

- **Language**: ECMAScript (JavaScript-like, QtScript engine)
- **API scope**: Full QCAD API + Qt framework access
- **Execution**: Headless via `qcad.exe -no-gui -autostart script.js`
- **MCP integration**: `plan_script` tool pipes ECMAScript from AI → QCAD Pro → results
- **Learning curve**: Low (JavaScript developers pick it up immediately)
- **Community**: Small but active forum; scripts bundled with QCAD Pro

### AutoCAD LT — AutoLISP / .NET / VBA

```lisp
;; Add a line
(command "_LINE" '(0 0) '(100 0) "")

;; Create a layer
(command "_LAYER" "N" "Walls" "C" "1" "Walls" "")
```

- **Languages**: AutoLISP (primary), .NET (C#/VB.NET), VBA, JavaScript (limited)
- **API scope**: Full AutoCAD object model
- **Execution**: In-process within AutoCAD LT
- **MCP integration**: Would require COM interop or socket bridge — no native headless CLI
- **Learning curve**: AutoLISP is esoteric; .NET requires Visual Studio toolchain
- **Community**: Massive (decades of AutoCAD ecosystem)

### Why ECMAScript Wins for MCP

1. **Headless execution**: QCAD Pro scripts run without GUI via simple CLI. AutoCAD LT has no equivalent headless mode.
2. **LLM-native language**: AI models generate ECMAScript reliably — it's just JavaScript. AutoLISP is an obscure 1986 Lisp dialect that LLMs struggle with and nobody outside CAD has used in 30 years.
3. **No library dependency**: AutoCAD's value proposition is its 40-year AutoLISP library ecosystem (Lee Mac, Cadtutor, The Swamp). With `plan_script`, **the LLM is the library** — it writes fresh ECMAScript for each task from first principles. No hunting for pre-written routines.
4. **Lightweight**: QCAD Pro starts in ~3 seconds for a script run. AutoCAD LT cold start is ~30+ seconds.
5. **One-time cost**: €42 vs. €550/year — viable for fleet automation.
6. **Cross-platform**: Runs on Linux servers; AutoCAD LT is Windows/macOS only.

## File Format Support

| Format | QCAD Pro | AutoCAD LT |
|---|---|---|
| DWG (native) | Read/write via Teigha (R12–R2023) | Native read/write |
| DXF | Full R12–R2023 | Full |
| PDF export | Built-in (dwg2pdf) | Built-in |
| SVG export | Built-in (dwg2svg) | Via plot driver |
| BMP/PNG export | Built-in (dwg2bmp) | Built-in |
| DGN (MicroStation) | No | Import only |
| STL (3D) | Via `plan_extrude` (this MCP server) | No |

## Platform Support

| | QCAD Pro | AutoCAD LT |
|---|---|---|
| Windows | Yes | Yes |
| macOS | Yes (Intel + Apple Silicon) | Yes (Apple Silicon via Rosetta) |
| Linux | Yes (native) | No |
| Headless/server | Yes (`-no-gui` flag) | No |

For MCP server deployments, QCAD Pro's Linux + headless support is decisive. AutoCAD LT cannot run on a headless Linux server.

## Who Should Use Which

### Choose QCAD Pro if:
- You're building MCP/agentic CAD tooling (this repo's use case)
- You need headless/server-side CAD processing
- Budget matters (€42 one-time vs. €550/year)
- You want AI to write CAD scripts (ECMAScript is more LLM-friendly than AutoLISP)
- You need Linux support
- Your work is primarily 2D architectural/drafting

### Choose AutoCAD LT if:
- You're in a DWG-centric office that standardizes on Autodesk
- You need parametric constraints or dynamic blocks
- You rely on the AutoCAD ecosystem (plugins, LISP routines, training)
- You need DGN import or industry-specific AutoCAD features
- You're doing mechanical/manufacturing drafting

## Summary

For the MCP use case, QCAD Pro is the clear winner: headless CLI, ECMAScript (LLM-friendly), €42 one-time, Linux support, cross-platform. AutoCAD LT is the industry standard for interactive drafting but was never designed for server-side automation — its scripting APIs require a running GUI and its subscription pricing makes fleet deployment expensive.

The two can coexist: draft interactively in AutoCAD LT, batch-process and automate via QCAD Pro through this MCP server.
