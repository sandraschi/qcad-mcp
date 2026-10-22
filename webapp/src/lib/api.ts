/**
 * Same-origin ("") by default — the Vite dev proxy and any reverse proxy
 * serve /api from the same host, so browser tabs on LAN/Tailscale names
 * (goliath, MagicDNS) pass the CORS path. An absolute backend URL is used
 * ONLY inside the Tauri WebView, where same-origin is the app bundle itself.
 * (2026-10-05 incident class: hardcoded 127.0.0.1 backend = dead dashboard
 * on every non-localhost tab while curl stayed green.)
 */
function isTauri(): boolean {
	return (
		typeof window !== "undefined" &&
		("__TAURI__" in window ||
			"__TAURI_INTERNALS__" in window ||
			window.location.protocol === "tauri:" ||
			window.location.hostname === "tauri.localhost")
	);
}

export const API_BASE = isTauri() ? "http://127.0.0.1:11966" : "";

export function apiPath(path: string): string {
	return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * v0.4.0 portmanteau surface: 8 domain tools (plan, plan_edit, plan_annotate,
 * plan_pro, plan_library, plan_ai, plan_bim, qcad) + 4 Prefab cards. Legacy
 * per-op names ("plan_info") are translated here so pages keep readable
 * call sites; the wire always carries the new tool + op discriminator.
 */
const LEGACY_TOOL_OPS: Record<string, { tool: string; op: string; renames?: Record<string, string> }> = {
	plan_info: { tool: "plan", op: "info" },
	plan_to_svg: { tool: "plan", op: "to_svg", renames: { layers: "svg_layers" } },
	plan_extrude: { tool: "plan", op: "extrude" },
	plan_stack: { tool: "plan", op: "stack" },
	plan_obj: { tool: "plan", op: "obj" },
	plan_glb: { tool: "plan", op: "glb" },
	plan_drawings: { tool: "plan", op: "drawings" },
	plan_export: { tool: "plan", op: "export" },
	plan_analyse: { tool: "plan", op: "analyse" },
	plan_create: { tool: "plan", op: "create" },
	plan_depot: { tool: "plan", op: "depot" },
	plan_convert: { tool: "plan_edit", op: "convert" },
	plan_modify: { tool: "plan_edit", op: "modify" },
	plan_dimension: { tool: "plan_annotate", op: "dimension" },
	plan_measure: { tool: "plan_annotate", op: "measure" },
	plan_text: { tool: "plan_annotate", op: "text" },
	plan_hatch: { tool: "plan_annotate", op: "hatch" },
	plan_block_insert: { tool: "plan_annotate", op: "block_insert" },
	plan_array: { tool: "plan_annotate", op: "array" },
	plan_wall_data: { tool: "plan_annotate", op: "wall_data" },
	plan_beam_analysis: { tool: "plan_annotate", op: "beam_analysis" },
	plan_blocks: { tool: "plan_library", op: "blocks" },
	plan_blocks_download: { tool: "plan_library", op: "blocks_download" },
	plan_scripts_search: { tool: "plan_library", op: "scripts_search" },
	plan_scripts_download: { tool: "plan_library", op: "scripts_download" },
	plan_script: { tool: "plan_pro", op: "script" },
	plan_render: { tool: "plan_pro", op: "render" },
	plan_exec: { tool: "plan_pro", op: "exec" },
	qcad_status: { tool: "qcad", op: "status" },
	qcad_help: { tool: "qcad", op: "help" },
	qcad_shutdown: { tool: "qcad", op: "shutdown" },
	plan_generate: { tool: "plan_ai", op: "generate" },
	plan_agentic: { tool: "plan_ai", op: "agentic" },
	plan_transpile: { tool: "plan_ai", op: "transpile" },
	cad_sampling: { tool: "plan_ai", op: "sampling" },
	plan_auto_dimension: { tool: "plan_bim", op: "auto_dimension" },
	plan_building_meta: { tool: "plan_bim", op: "building_meta" },
	plan_to_ifc_data: { tool: "plan_bim", op: "to_ifc_data" },
};

export function toolCallBody(
	tool: string,
	args: Record<string, unknown> = {},
): {
	tool: string;
	arguments: Record<string, unknown>;
} {
	const mapped = LEGACY_TOOL_OPS[tool];
	if (!mapped) return { tool, arguments: args };
	const out: Record<string, unknown> = { op: mapped.op };
	for (const [k, v] of Object.entries(args)) {
		out[mapped.renames?.[k] ?? k] = v;
	}
	return { tool: mapped.tool, arguments: out };
}

export async function callControlTool<T = unknown>(tool: string, args: Record<string, unknown> = {}): Promise<T> {
	const r = await fetch(apiPath("/api/v1/control/tool"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(toolCallBody(tool, args)),
	});
	if (!r.ok) {
		const text = await r.text();
		throw new Error(`${tool} failed (${r.status}): ${text.slice(0, 200)}`);
	}
	return r.json() as Promise<T>;
}

/** Patch fetch/EventSource for Tauri production (relative /api paths). */
export function installTauriApiShim(): void {
	if (import.meta.env.DEV) return;

	const base = API_BASE;
	const origFetch = window.fetch.bind(window);
	window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
		if (typeof input === "string" && input.startsWith("/")) {
			return origFetch(base + input, init);
		}
		return origFetch(input, init);
	};

	const OrigES = window.EventSource;
	window.EventSource = class PatchedEventSource extends OrigES {
		constructor(url: string | URL, config?: EventSourceInit) {
			const resolved = typeof url === "string" && url.startsWith("/") ? base + url : url;
			super(resolved, config);
		}
	} as typeof EventSource;
}
