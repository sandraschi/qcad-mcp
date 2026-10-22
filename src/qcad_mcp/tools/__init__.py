"""QCAD MCP tools - portmanteau registration (v0.5.0 surface).

[RATIONALE] Single entry point registering 8 domain portmanteaus
(plan, plan_edit, plan_annotate, plan_pro, plan_library, plan_ai,
plan_bim, qcad) plus 4 Prefab display cards = 12 tools total.
Per-op coroutines stay importable in their modules (tests, server
internals, REST bridge delegate to them); only the MCP surface is
consolidated so LLM tool-list context stays lean.

Domain skills (skills/*/SKILL.md) are additionally exposed over MCP
via fastmcp's SkillsDirectoryProvider (skill:// URIs), so sampling
clients can discover them without the REST /api/skills hop.
"""

import logging
from pathlib import Path

logger = logging.getLogger("qcad-mcp")


def register_all(mcp):
    from qcad_mcp.tools.portmanteau import register as reg_portmanteau
    from qcad_mcp.tools.prefab_cards import register as reg_prefab

    reg_portmanteau(mcp)
    reg_prefab(mcp)

    try:
        from fastmcp.server.providers.skills import SkillsDirectoryProvider

        skills_dir = Path(__file__).resolve().parents[3] / "skills"
        if skills_dir.is_dir():
            mcp.add_provider(SkillsDirectoryProvider(roots=[skills_dir]))
        else:
            logger.debug("Skills dir missing, skipping SkillsDirectoryProvider: %s", skills_dir)
    except Exception as e:
        logger.debug("SkillsDirectoryProvider unavailable: %s", e)
