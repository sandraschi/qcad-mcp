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
