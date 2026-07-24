import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, Maximize2, Minimize2, RefreshCw } from "lucide-react";
import { useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useConnection } from "../store/connection";
import { useZoom } from "../hooks/useZoom";
import { API_BASE } from "../lib/api";

const PAGE_TITLES: Record<string, string> = {
	"/": "Dashboard",
	"/demo": "AI CAD Demo",
	"/agentic": "AI Agent",
	"/depot": "CAD Depot",
	"/viewer": "Floor Plan Viewer",
	"/extrude": "3D Extrusion",
	"/analyse": "Room Analysis",
	"/layers": "Layer Manager",
	"/blocks": "Block Library",
	"/scripts": "Script Library",
	"/batch": "Batch Processing",
	"/pipeline": "Pipeline",
	"/models": "Model Outputs",
	"/logs": "Logs",
	"/settings": "Settings",
	"/help": "Help & Reference",
};

const BACKOFF = [1, 2, 4, 8, 16, 30];

export default function AppLayout({ children }: { children: React.ReactNode }) {
	useZoom();
	const [collapsed, setCollapsed] = useState(false);
	const { state, lastError } = useConnection();
	const location = useLocation();
	const pageTitle = PAGE_TITLES[location.pathname] || "QCAD MCP";
	const attemptRef = useRef(0);
	const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

	const tick = useCallback(async () => {
		try {
			const r = await fetch(`${API_BASE}/api/v1/status`, { signal: AbortSignal.timeout(5000) });
			if (r.ok) { useConnection.setState({ state: "connected" }); attemptRef.current = 0; }
			else useConnection.setState({ state: "offline", lastError: `HTTP ${r.status}` });
		} catch (e) {
			useConnection.setState({ state: "offline", lastError: (e as Error).message });
		}
		attemptRef.current = Math.min(++attemptRef.current, BACKOFF.length - 1);
		timerRef.current = setTimeout(tick, BACKOFF[attemptRef.current] * 1000);
	}, []);

	useEffect(() => {
		tick();
		(async () => {
			try {
				const { listen } = await import("@tauri-apps/api/event");
				const unlisten = await listen<string>("backend-status", (event) => {
					if (event.payload === "ready") useConnection.setState({ state: "connected" });
					else if (event.payload?.startsWith("error:")) useConnection.setState({ state: "error", lastError: event.payload });
				});
				return () => { unlisten(); clearTimeout(timerRef.current); };
			} catch { return () => clearTimeout(timerRef.current); }
		})();
		return () => clearTimeout(timerRef.current);
	}, [tick]);

	const statusColor = state === "connected" ? "text-emerald-400" :
		state === "connecting" ? "text-amber-400" : "text-red-400";

	const statusLabel = state === "connected" ? "Server Ready" :
		state === "connecting" ? "Connecting..." : `Offline${lastError ? ` (${lastError.slice(0, 60)})` : ""}`;

	const handleRestart = async () => {
		try {
			const { invoke } = await import("@tauri-apps/api/core");
			await invoke("start_backend");
		} catch { /* not in Tauri */ }
	};

	return (
		<div className="flex h-full">
			<Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
			<div className="flex-1 flex flex-col overflow-hidden">
		<header className="h-12 flex items-center justify-between px-6 border-b border-white/10 bg-[#0a0a0c] shrink-0">
				<div className="flex items-center gap-3">
					<h2 className="text-sm font-bold text-white tracking-wide">{pageTitle}</h2>
				</div>
				<div className="flex items-center gap-3">
					<button type="button" onClick={() => window.open(window.location.href, "_blank")} title="Pop Out" className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all">
						<ExternalLink size={14} />
					</button>
					<button type="button" onClick={() => { try { window.open("", "", "width=1100,height=750"); } catch {} }} title="Companion Mode" className="p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all">
						<Maximize2 size={14} />
					</button>
					<div className="w-px h-4 bg-white/10" />
					<div className="flex items-center gap-2 text-sm">
						<span data-testid="connection-status" className={`w-2 h-2 rounded-full ${statusColor} bg-current`} />
						<span data-testid="connection-label" className={statusColor}>{statusLabel}</span>
						{state !== "connected" && (
							<button data-testid="restart-backend" onClick={handleRestart} title="Restart Backend" className="ml-1 text-slate-400 hover:text-white transition-colors">
								<RefreshCw className="w-3 h-3" />
							</button>
						)}
					</div>
				</div>
			</header>
				<main className="flex-1 overflow-y-auto p-6">{children}</main>
			</div>
		</div>
	);
}


