# qcad-mcp — Copilot instructions

## Session Context (qcad-mcp)
Before starting work: call `plan_depot` to see depot files, `qcad_status`
for QCAD Pro state. DXF lives in `%LOCALAPPDATA%\qcad-mcp\depot`.
At end of work: run `uv run pytest tests/ -q`, update CHANGELOG.md,
never commit `dist/`, `mcpb/src/`, or `.env`.
