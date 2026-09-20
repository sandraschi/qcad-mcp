"""LLM floor-plan generation: natural language -> plan_create entity JSON.

The Demo webapp's free-text box posts to ``POST /api/v1/ai/generate-plan``
(which lives in ``server.py`` and delegates here) *before* falling back to
the keyword templates baked into the webapp. Templates are the fallback,
never the primary path.

Only the local Ollama engine is used (fleet local-LLM-first). There is no
model fallback: if no model is selected in Settings, generation refuses
with ``PlanLlmError("no-model")`` and the caller falls back to templates.
"""

from __future__ import annotations

import json
import logging
import math

import httpx

logger = logging.getLogger("qcad-mcp")

MAX_ENTITIES = 300
MAX_LEVELS = 8
MAX_COORD = 600_000.0  # mm (600 m) -- sanity bound for a floor plan
NUM_CTX = 8192  # floor-plan JSON needs <4k tokens; larger ctx spills to CPU (slow)

LAYER_COLORS = {
    "Walls": 7,
    "Columns": 8,
    "Doors": 3,
    "Windows": 1,
    "Furniture": 6,
    "Text": 2,
    "Dimensions": 6,
    "Detail": 5,
    "Slab": 8,
}

_DEFAULT_LAYER = {
    "line": "Walls",
    "rect": "Walls",
    "circle": "Columns",
    "arc": "Walls",
    "polyline": "Walls",
    "door": "Doors",
    "window": "Windows",
    "text": "Text",
}

# Required key groups per entity type. A group is satisfied when ALL its keys
# are present. Mirrors the lenient aliases plan_create accepts (x1/y1/x2/y2
# shapes from the webapp, x/y/w/h shapes from MCP clients).
_REQUIRED = {
    "line": [("x1", "y1", "x2", "y2")],
    "rect": [("x1", "y1", "x2", "y2"), ("x", "y", "w", "h")],
    "circle": [("x", "y", "r"), ("cx", "cy", "r")],
    "arc": [("cx", "cy", "r", "start_angle", "end_angle"), ("x", "y", "r", "start_angle", "end_angle")],
    "polyline": [("points",)],
    "door": [("x", "y", "w")],
    "window": [("x1", "y1", "x2", "y2")],
    "text": [("x", "y", "text"), ("x", "y", "content")],
}

_NUMERIC_KEYS = {
    "x1",
    "y1",
    "x2",
    "y2",
    "x",
    "y",
    "w",
    "h",
    "r",
    "cx",
    "cy",
    "angle",
    "start_angle",
    "end_angle",
    "hgt",
    "height",
    "elevation",
}


class PlanLlmError(Exception):
    """Refusal with a machine-readable code: no-model, ollama, json, plan."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


SYSTEM_PROMPT = """You design 2D architectural floor plans as structured JSON for a CAD pipeline.
Output ONLY a single JSON object, no prose, no fences.

Coordinate system: 2D plan view, X right, Y up. Units are MILLIMETRES (integers preferred):
a 10m x 8m building is x 0..10000, y 0..8000. Wall height overrides use "hgt" in METRES.

Entity types (keys mirror the plan_create tool):
- {"type":"rect","x1":0,"y1":0,"x2":10000,"y2":8000,"layer":"Walls"} outer walls / rooms
- {"type":"line","x1":0,"y1":0,"x2":1000,"y2":0,"layer":"Walls"} interior partitions
- {"type":"circle","x":5000,"y":4000,"r":200,"layer":"Columns"} columns
- {"type":"arc","cx":10000,"cy":4000,"r":6000,"start_angle":-90,"end_angle":90,"layer":"Walls"} curved walls
- {"type":"door","x":4500,"y":0,"w":900,"angle":0,"layer":"Doors"} door opening (w = leaf mm)
- {"type":"window","x1":2000,"y1":8000,"x2":3500,"y2":8000,"layer":"Windows"} window in a wall
- {"type":"text","x":4000,"y":4000,"h":300,"text":"LIVING","layer":"Text"} room label
- {"type":"polyline","points":[[0,0],[1000,0],[1000,500]],"closed":false,"layer":"Detail"}

Layers (use exactly these names): Walls, Columns, Doors, Windows, Furniture, Text, Dimensions, Detail.
Give long walls "hgt" only when the goal names a special height (nave 12, tower 25); else omit it.

Shape:
{"entities":[...], "layers":[{"name":"Walls","color":7},...], "inserts":[]}
Multi-storey goals (tower, storeys, levels, floors) instead use:
{"levels":[{"suffix":"L0","title":"Ground floor","elevation":0,"entities":[...],"inserts":[]},...],
 "layers":[...]}
with elevation in METRES per storey. Max 8 levels, max 300 entities per scope.

Example: {"entities":[
 {"type":"rect","x1":0,"y1":0,"x2":6000,"y2":5000,"layer":"Walls"},
 {"type":"line","x1":3000,"y1":0,"x2":3000,"y2":5000,"layer":"Walls"},
 {"type":"door","x":2700,"y":0,"w":900,"angle":0,"layer":"Doors"},
 {"type":"window","x1":1000,"y1":5000,"x2":2500,"y2":5000,"layer":"Windows"},
 {"type":"text","x":1000,"y":2500,"h":300,"text":"ROOM 1","layer":"Text"},
 {"type":"text","x":4000,"y":2500,"h":300,"text":"ROOM 2","layer":"Text"}],
 "layers":[{"name":"Walls","color":7},{"name":"Doors","color":3},{"name":"Windows","color":1},{"name":"Text","color":2}],
 "inserts":[]}

Rules: real dimensions from the goal (a 40m museum is 40000 wide, not 4000).
Rooms get doors; outer walls get windows; every room gets a text label.
Keep it buildable: closed outer rectangle first, then partitions, then openings.
Never emit prose, never emit code, only the JSON object."""


def build_user_prompt(goal: str) -> str:
    """Wrap the free-text goal with output-shape instructions."""
    return (
        f"Floor plan goal: {goal.strip()}\n\n"
        "Respond with ONLY the JSON object (single storey => entities, "
        "multi-storey => levels). No explanation."
    )


def extract_plan_json(text: str) -> dict:
    """Pull the JSON object out of chat output (fences / prose tolerated)."""
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        # drop opening fence (``` or ```json) and trailing fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    if not raw.startswith("{"):
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise PlanLlmError("json", "LLM output contains no JSON object.")
        raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PlanLlmError("json", f"LLM output is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise PlanLlmError("json", "LLM output JSON is not an object.")
    return data


def _is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _round2(v: float) -> float:
    return round(float(v), 2)


def _clean_entity(ent: object) -> dict | None:
    """Return a sanitised entity or None (with the reason logged)."""
    if not isinstance(ent, dict):
        logger.debug("plan_llm: dropping non-object entity %r", ent)
        return None
    etype = ent.get("type")
    if etype not in _REQUIRED:
        logger.debug("plan_llm: dropping unknown entity type %r", etype)
        return None
    groups = _REQUIRED[etype]  # type: ignore[index]
    if not any(all(k in ent for k in g) for g in groups):
        logger.debug("plan_llm: dropping %s with missing keys %r", etype, ent)
        return None
    out: dict = {"type": etype}
    for k, v in ent.items():
        if k in _NUMERIC_KEYS:
            if not _is_num(v):
                logger.debug("plan_llm: dropping %s with non-numeric %s=%r", etype, k, v)
                return None
            out[k] = _round2(v)
        elif k == "points":
            if (
                not isinstance(v, list)
                or len(v) < 2
                or any(not isinstance(p, (list, tuple)) or len(p) != 2 or not all(_is_num(n) for n in p) for p in v)
            ):
                logger.debug("plan_llm: dropping polyline with bad points")
                return None
            out[k] = [[_round2(a), _round2(b)] for a, b in v]
        elif k == "text" or k == "content":
            if not isinstance(v, str) or not v.strip():
                logger.debug("plan_llm: dropping text with empty content")
                return None
            out[k] = v.strip()[:200]
        elif k == "layer":
            out[k] = v if isinstance(v, str) and v else _DEFAULT_LAYER[etype]
        elif k in ("closed",):
            out[k] = bool(v)
        elif k in ("hgt", "height"):
            continue  # handled below (already copied as numeric)
        elif isinstance(v, (str, int, float, bool)):
            out[k] = v
    out.setdefault("layer", _DEFAULT_LAYER[etype])
    # Bounds: coordinates in mm, sizes positive.
    for k in ("x1", "y1", "x2", "y2", "x", "y", "cx", "cy"):
        if k in out and abs(out[k]) > MAX_COORD:
            logger.debug("plan_llm: dropping %s out of bounds (%s=%s)", etype, k, out[k])
            return None
    for k in ("w", "r"):
        if k in out and not (0 < out[k] <= MAX_COORD):
            logger.debug("plan_llm: dropping %s with bad size (%s=%s)", etype, k, out[k])
            return None
    if "h" in out and not (0 < out["h"] <= 10000):
        out["h"] = 250.0
    for k in ("hgt", "height"):
        if k in out and not (0.2 <= out[k] <= 50):
            del out[k]
    return out


def _clean_layers(layers: object, used: set[str]) -> list[dict]:
    defs: list[dict] = []
    seen: set[str] = set()
    if isinstance(layers, list):
        for item in layers:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            name = item["name"].strip() or "Walls"
            color = item.get("color")
            defs.append(
                {
                    "name": name,
                    "color": color if isinstance(color, int) else LAYER_COLORS.get(name, 7),
                    "description": f"{name} lines",
                }
            )
            seen.add(name)
    for name in sorted(used - seen):
        defs.append({"name": name, "color": LAYER_COLORS.get(name, 7), "description": f"{name} lines"})
    return defs or [{"name": "Walls", "color": 7, "description": "Wall lines"}]


def _clean_inserts(inserts: object) -> list[dict]:
    out: list[dict] = []
    if not isinstance(inserts, list):
        return out
    for item in inserts:
        if not isinstance(item, dict):
            continue
        name = item.get("block_name")
        if not isinstance(name, str) or not name.strip():
            continue
        if not _is_num(item.get("x")) or not _is_num(item.get("y")):
            continue
        if abs(item["x"]) > MAX_COORD or abs(item["y"]) > MAX_COORD:
            continue
        layer = item.get("layer")
        out.append(
            {
                "block_name": name.strip().upper()[:32],
                "x": _round2(item["x"]),
                "y": _round2(item["y"]),
                "layer": layer if isinstance(layer, str) and layer else "Furniture",
            }
        )
    return out


def validate_plan(data: dict) -> tuple[dict, list[str]]:
    """Validate LLM output. Returns (spec, warnings); raises PlanLlmError."""
    warnings: list[str] = []
    levels: list[dict] | None = None
    raw_levels = data.get("levels")
    if isinstance(raw_levels, list) and raw_levels:
        if len(raw_levels) > MAX_LEVELS:
            warnings.append(f"{len(raw_levels)} levels requested, keeping first {MAX_LEVELS}.")
            raw_levels = raw_levels[:MAX_LEVELS]
        levels = []
        for i, lv in enumerate(raw_levels):
            if not isinstance(lv, dict):
                warnings.append(f"Level {i} is not an object, dropped.")
                continue
            ents = [_clean_entity(e) for e in lv.get("entities", [])] if isinstance(lv.get("entities"), list) else []
            valid = [e for e in ents if e is not None]
            dropped = len(ents) - len(valid)
            if dropped:
                warnings.append(f"Level {i}: dropped {dropped} invalid entities.")
            if len(valid) > MAX_ENTITIES:
                warnings.append(f"Level {i}: keeping first {MAX_ENTITIES} of {len(valid)} entities.")
                valid = valid[:MAX_ENTITIES]
            if not valid:
                warnings.append(f"Level {i}: no usable entities, dropped.")
                continue
            elev = lv.get("elevation", 3.5 * i)
            elev = _round2(elev) if _is_num(elev) and 0 <= elev <= 200 else round(3.5 * i, 2)
            used = {e["layer"] for e in valid}
            levels.append(
                {
                    "suffix": str(lv.get("suffix", f"L{i}"))[:16] or f"L{i}",
                    "title": str(lv.get("title", f"Level {i}"))[:80] or f"Level {i}",
                    "elevation": elev,
                    "entities": valid,
                    "layers": _clean_layers(lv.get("layers"), used),
                    "inserts": _clean_inserts(lv.get("inserts")),
                }
            )
        if not levels:
            raise PlanLlmError("plan", "LLM returned levels but none contained usable entities.")
        used_all = {layer["name"] for lv in levels for layer in lv["layers"]}
        return (
            {"entities": [], "layers": _clean_layers(data.get("layers"), used_all), "inserts": [], "levels": levels},
            warnings,
        )

    if not isinstance(data.get("entities"), list) or not data["entities"]:
        raise PlanLlmError("plan", "LLM returned no entities and no levels.")
    ents = [_clean_entity(e) for e in data["entities"]]
    valid = [e for e in ents if e is not None]
    dropped = len(ents) - len(valid)
    if dropped:
        warnings.append(f"Dropped {dropped} invalid entities.")
    if len(valid) > MAX_ENTITIES:
        warnings.append(f"Keeping first {MAX_ENTITIES} of {len(valid)} entities.")
        valid = valid[:MAX_ENTITIES]
    if not valid:
        raise PlanLlmError("plan", "LLM returned entities but none were usable.")
    used = {e["layer"] for e in valid}
    return (
        {
            "entities": valid,
            "layers": _clean_layers(data.get("layers"), used),
            "inserts": _clean_inserts(data.get("inserts")),
        },
        warnings,
    )


async def chat_generate(goal: str, model: str, ollama_url: str, timeout_s: float = 300.0) -> str:
    """Call local Ollama chat with JSON mode. Returns raw message content."""
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(
                f"{ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(goal)},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"num_ctx": NUM_CTX, "num_predict": 4096, "temperature": 0.2},
                },
            )
    except Exception as e:
        raise PlanLlmError("ollama", f"Ollama unreachable at {ollama_url}: {e}") from e
    try:
        data = r.json()
    except Exception:
        data = {}
    if r.status_code != 200:
        detail = data.get("error", "") if isinstance(data, dict) else ""
        raise PlanLlmError("ollama", f"Ollama error: {detail or (r.text or '')[:200]}")
    content = (data.get("message") or {}).get("content", "") if isinstance(data, dict) else ""
    if not content or not content.strip():
        raise PlanLlmError("ollama", f"Ollama returned no content (model '{model}' installed?).")
    return content


def load_server_llm_settings() -> tuple[str, str]:
    """Model + Ollama URL from the persisted settings file.

    Lets MCP tools (no access to the server's in-memory settings) honour the
    model picked in Settings > LLM Provider. Returns ("", default_url) when
    nothing was ever saved.
    """
    import os

    default_url = "http://127.0.0.1:11434"
    path = os.environ.get("QCAD_SETTINGS_FILE") or os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "qcad-mcp", "settings.json"
    )
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            model = data.get("model") or ""
            url = data.get("ollama_url") or default_url
            return (model if isinstance(model, str) else "", url if isinstance(url, str) else default_url)
    except Exception:
        pass
    return "", default_url
