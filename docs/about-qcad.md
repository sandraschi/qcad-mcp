# About QCAD

## What is QCAD?

**QCAD** is a professional 2D CAD application built on the DXF format. Swiss-made by RibbonSoft, it has been in development since 1999. It reads and writes DXF and DWG files — the industry standard for 2D construction drawings, floor plans, and mechanical drafting.

Two editions:

| Edition | License | Price | DWG Support | PDF Export | CLI Tools |
|:---|:---|:---|:---|:---|:---|
| **Community** | GPLv2 | Free | No | Basic | No |
| **Professional** | Proprietary | ~€50.40 | Yes | High-fidelity | Yes (dwg2pdf, dwg2svg) |

## History

| Year | Milestone |
|:---|:---|
| 1999 | Initial development by RibbonSoft (Switzerland) |
| 2004 | First stable release |
| 2010 | Open-source Community Edition launched |
| 2015 | Professional Edition with DWG support |
| 2020 | Qt5 port, modern UI |
| 2024 | Current stable — mature DXF/R12-R2023 support |

## ezdxf — The Core Engine

This MCP server uses **ezdxf** (by Manfred Moitzi) rather than QCAD itself. ezdxf is a pure-Python library (MIT license) that handles all DXF operations without any binary dependencies.

**Key capabilities:**
- Reads DXF from R12 (1985) through R2023
- Handles all common entity types: LINE, LWPOLYLINE, CIRCLE, ARC, TEXT, MTEXT, INSERT, HATCH, SPLINE, DIMENSION
- Layer, block, linetype, and style management
- Bounding box and extents calculation
- DXF creation from scratch

**Why ezdxf over QCAD CLI?**
- Pure Python — no external process, no Windows dependency
- MIT licensed — no commercial restrictions
- Faster for batch processing (no GUI framework startup)
- Full control over entity geometry in Python

**Why still have QCAD Pro as an option?**
- DWG file reading (ezdxf has limited DWG support)
- Higher quality PDF rendering (fonts, line weights)
- Better compatibility with complex AutoCAD files

## Comparison: QCAD vs AutoCAD

| Aspect | QCAD | AutoCAD |
|:---|:---|:---|
| **License** | GPLv2 / €50.40 | $2,000+/year |
| **File Format** | DXF (native), DWG (Pro) | DWG (native) |
| **2D Drafting** | Full | Full |
| **3D** | No | Yes |
| **Scripting** | ECMAScript (QtScript) | AutoLISP, .NET, VBA |
| **Python API** | Via ezdxf (separate) | Via pyautocad (limited) |
| **BIM** | No | Yes (Revit integration) |
| **Platform** | Windows, macOS, Linux | Windows, Mac |
| **Learning Curve** | Gentle | Steep |
| **LISP Support** | Partial | Full |
| **DWG Write** | Pro only | Yes |

## QCAD Scripting

QCAD uses **ECMAScript** (QtScript, similar to JavaScript) for scripting and automation. Scripts can:
- Create and modify entities
- Read/write files
- Access the drawing database
- Add custom tools to the UI

The Community Edition includes the Script Editor (ECMAScript IDE) for writing and running scripts. QCAD Pro adds additional scripting capabilities for DWG operations.

However, for programmatic access, **ezdxf** (Python) is the better choice — it's what this MCP server uses internally.

## QCAD in the Fleet

This MCP server turns QCAD/ezdxf into an AI-accessible service. The typical pipeline:

```
Floor plan (DXF) → plan_extrude → STL → freecad-mcp (optimise) → 3D print or game engine
```

Other fleet integrations:
- **freecad-mcp**: Post-process STL extrusions for 3D printing
- **resonite-mcp / unity3d-mcp**: Import STL floor plans into virtual worlds
- **robo-fang**: Automate floor plan processing as a background job
