---
name: qcad
description: QCAD 2D CAD automation over MCP - depot files, DXF metadata, SVG preview, STL extrusion, QCAD Pro bridge.
---

# qcad-mcp

## Session Context (qcad-mcp)
Before starting work: call `plan_depot` to see depot files, `qcad_status`
for QCAD Pro state. DXF lives in `%LOCALAPPDATA%\qcad-mcp\depot`.
At end of work: run `uv run pytest tests/ -q`, update CHANGELOG.md,
never commit `dist/`, `mcpb/src/`, or `.env`.

## Tool catalog
Core (ezdxf, no QCAD Pro): plan_info, plan_to_svg, plan_extrude, plan_analyse,
plan_create, plan_depot, plan_modify, plan_convert, plan_wall_data, plan_beam_analysis.
QCAD Pro: qcad_status, plan_script, plan_render, plan_exec, plan_dimension,
plan_measure, plan_text, plan_hatch, plan_block_insert, plan_array.
Library: plan_blocks, plan_blocks_download, plan_scripts_search,
plan_scripts_download. Agentic: plan_agentic, plan_transpile.
Meta: qcad_help, qcad_shutdown.
