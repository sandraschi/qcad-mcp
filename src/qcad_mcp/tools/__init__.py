"""QCAD MCP tools — portmanteau registration for FastMCP 3.2.

All tools are registered via register_all(mcp) which each module's
register() function. This ensures @mcp.tool decorators fire at boot.
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
