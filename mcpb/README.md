# qcad-mcp (MCPB Bundle)

QCAD MCP server — DXF/DWG floor plans to SVG preview + STL extrusion via MCP tools and REST API

## Usage

Add to \claude_desktop_config.json\:
\\\json
{
  "mcpServers": {
    "qcad-mcp": {
      "command": "uv",
      "args": ["run", "--directory", "\D:\Dev\repos", "python", "-m", "qcad_mcp"],
      "env": { "PYTHONPATH": "\D:\Dev\repos/src" }
    }
  }
}
\\\

## Tools

- **qcad-mcp**: QCAD MCP server — DXF/DWG floor plans to SVG preview + STL extrusion via MCP tools and REST API

## Requirements

- Python 3.12+
- uv
