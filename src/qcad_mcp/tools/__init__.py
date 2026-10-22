"""QCAD MCP tools - portmanteau registration (v0.5.0 surface).

[RATIONALE] Single entry point registering 8 domain portmanteaus
(plan, plan_edit, plan_annotate, plan_pro, plan_library, plan_ai,
plan_bim, qcad) plus 4 Prefab display cards = 12 tools total.
Per-op coroutines stay importable in their modules (tests, server
internals, REST bridge delegate to them); only the MCP surface is
consolidated so LLM tool-list context stays lean.
"""


def register_all(mcp):
    from qcad_mcp.tools.portmanteau import register as reg_portmanteau
    from qcad_mcp.tools.prefab_cards import register as reg_prefab

    reg_portmanteau(mcp)
    reg_prefab(mcp)
