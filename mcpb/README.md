# qcad-mcp (MCPB Bundle)

QCAD MCP server - DXF/DWG floor plans to SVG preview + STL extrusion via MCP tools and REST API

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

- **api_status**: Server status including QCAD Pro and ezdxf info.
- **api_health**: Health endpoint with component status.
- **api_diagnostics**: api_diagnostics
- **blocks_categories**: List CAD block categories.
- **blocks_search**: Search CAD block libraries via REST.
- **blocks_download**: Download a CAD block to the depot via REST.
- **scripts_categories**: List ECMAScript script categories.
- **scripts_search**: Search ECMAScript libraries via REST.
- **scripts_download**: Download an ECMAScript to the depot via REST.
- **batch_run**: batch_run
- **get_layers**: Get layers for a DXF/DWG file.
- **update_layers**: Modify layers on a file.
- **depot_list**: depot_list
- **depot_get**: depot_get
- **depot_rename**: depot_rename
- **depot_delete**: depot_delete
- **depot_create**: depot_create
- **upload_file**: upload_file
- **download_file**: download_file
- **list_files**: list_files
- **execute_tool**: execute_tool
- **stream_logs**: stream_logs
- **llm_providers**: llm_providers
- **llm_chat**: llm_chat
- **get_settings**: get_settings
- **update_settings**: update_settings
- **chat_completion**: chat_completion
- **Building_1**: Building_1
- **Level_0**: Level_0
- **walls**: walls

## Requirements

- Python 3.12+
- uv
