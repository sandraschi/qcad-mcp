"""QCAD MCP tools — portmanteau registration for FastMCP 3.2.

[RATIONALALE] Consolidates 22 tools across 7 modules into a single register_all()
entry point. Each module's register() function fires @mcp.tool decorators at
import time for server boot discovery. Without this portmanteau, individual
tool modules would need manual import by operators.
"""


def register_all(mcp):
    from qcad_mcp.tools.agentic_tools import register as reg_agentic
    from qcad_mcp.tools.annotation_tools import register as reg_annot
    from qcad_mcp.tools.block_tools import register as reg_blocks
    from qcad_mcp.tools.core_tools import register as reg_core
    from qcad_mcp.tools.modify_tools import register as reg_modify
    from qcad_mcp.tools.qcad_tools import register as reg_qcad
    from qcad_mcp.tools.script_tools import register as reg_scripts

    reg_core(mcp)
    reg_modify(mcp)
    reg_blocks(mcp)
    reg_qcad(mcp)
    reg_annot(mcp)
    reg_agentic(mcp)
    reg_scripts(mcp)
