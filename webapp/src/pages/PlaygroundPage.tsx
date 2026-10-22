import { AlertTriangle, CheckCircle, Code2, Loader2, Play, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { API_BASE } from "../lib/api";

const TOOLS = ["plan", "plan_edit", "plan_annotate", "plan_pro", "plan_library", "plan_ai", "plan_bim", "qcad"];

const ARG_TEMPLATES: Record<string, string> = {
	plan: JSON.stringify({ op: "info", file_name: "studio_apt.dxf" }, null, 2),
	plan_edit: JSON.stringify(
		{ op: "modify", file_name: "studio_apt.dxf", operations: [{ op: "layer-freeze", layer_filter: "Furniture" }] },
		null,
		2,
	),
	plan_annotate: JSON.stringify({ op: "measure", file_name: "studio_apt.dxf" }, null, 2),
	plan_pro: JSON.stringify({ op: "exec", code: "print(transientEntityCount());" }, null, 2),
	plan_library: JSON.stringify({ op: "blocks", query: "door", limit: 5 }, null, 2),
	plan_ai: JSON.stringify({ op: "sampling", goal: "What wall height suits a residential floor plan?" }, null, 2),
	plan_bim: JSON.stringify({ op: "building_meta", file_name: "studio_apt.dxf" }, null, 2),
	qcad: JSON.stringify({ op: "status" }, null, 2),
};

export default function PlaygroundPage() {
	const [searchParams] = useSearchParams();
	const initialTool =
		searchParams.get("tool") && TOOLS.includes(searchParams.get("tool") as string)
			? (searchParams.get("tool") as string)
			: "plan";
	const [tool, setTool] = useState(initialTool);
	const [argsText, setArgsText] = useState("");
	const [result, setResult] = useState<string | null>(null);
	const [running, setRunning] = useState(false);
	const [error, setError] = useState("");
	const [depotFiles, setDepotFiles] = useState<string[]>([]);

	useEffect(() => {
		fetch(API_BASE + "/api/v1/files")
			.then((r) => r.json())
			.then((j) => {
				const all = [...(j.uploads || []), ...(j.outputs || [])].map((f: { name: string }) => f.name);
				setDepotFiles(all);
			})
			.catch(() => {});
	}, []);

	useEffect(() => {
		setArgsText(ARG_TEMPLATES[tool] || "{}");
		setResult(null);
		setError("");
	}, [tool]);

	const execute = useCallback(async () => {
		setRunning(true);
		setResult(null);
		setError("");
		try {
			const parsed = JSON.parse(argsText);
			const r = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ tool, arguments: parsed }),
			});
			const body = await r.json();
			setResult(JSON.stringify(body, null, 2));
			if (!r.ok) setError(`HTTP ${r.status}`);
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : String(e);
			setError(msg);
			setResult(null);
		} finally {
			setRunning(false);
		}
	}, [tool, argsText]);

	const insertFileName = (name: string) => {
		try {
			const parsed = JSON.parse(argsText);
			if (parsed.file_name === undefined && parsed.filename === undefined) {
				parsed.file_name = name;
			} else if (parsed.file_name !== undefined) {
				parsed.file_name = name;
			} else {
				parsed.filename = name;
			}
			setArgsText(JSON.stringify(parsed, null, 2));
		} catch {}
	};

	return (
		<div className="max-w-6xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Terminal className="text-amber-400" /> Tool Playground
			</h1>
			<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
				<div className="space-y-4">
					<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-4">
						<label htmlFor="pg-tool" className="text-sm text-slate-300">
							Tool
						</label>
						<select
							id="pg-tool"
							value={tool}
							onChange={(e) => setTool(e.target.value)}
							className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-amber-500"
						>
							{TOOLS.map((t) => (
								<option key={t} value={t}>
									{t}
								</option>
							))}
						</select>
					</div>
					<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-3">
						<div className="flex items-center justify-between">
							<label htmlFor="pg-args" className="text-sm text-slate-300">
								Arguments (JSON)
							</label>
							{depotFiles.length > 0 && (
								<div className="flex items-center gap-1">
									<span className="text-sm text-slate-300">Files:</span>
									<select
										onChange={(e) => {
											if (e.target.value) insertFileName(e.target.value);
											e.target.value = "";
										}}
										className="bg-black/40 border border-white/10 rounded text-sm px-2 py-1 text-slate-300 max-w-[140px]"
									>
										<option value="">Insert file name...</option>
										{depotFiles.map((f) => (
											<option key={f} value={f}>
												{f}
											</option>
										))}
									</select>
								</div>
							)}
						</div>
						<textarea
							id="pg-args"
							value={argsText}
							onChange={(e) => setArgsText(e.target.value)}
							rows={12}
							className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm font-mono text-emerald-300 placeholder-slate-600 focus:outline-none focus:border-amber-500 resize-none"
						/>
						<button
							type="button"
							onClick={execute}
							disabled={running}
							className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold w-full justify-center"
						>
							{running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
							{running ? "Executing..." : `Execute ${tool}`}
						</button>
						{error && (
							<div className="flex items-start gap-2 text-red-400 text-sm bg-red-950/30 border border-red-500/20 rounded-xl p-3">
								<AlertTriangle size={14} className="shrink-0 mt-0.5" />
								<span>{error}</span>
							</div>
						)}
					</div>
				</div>
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
					<div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
						<Code2 size={14} className="text-amber-400" />
						<span className="text-sm font-bold text-slate-300 uppercase tracking-wider">Response</span>
						{result && <span className="text-sm text-slate-300 ml-auto">{result.length} bytes</span>}
					</div>
					<pre className="p-4 text-xs font-mono text-slate-300 overflow-auto max-h-[600px] whitespace-pre-wrap">
						{result || <span className="text-slate-600">Execute a tool to see the response here.</span>}
					</pre>
					{result && (
						<div className="px-4 py-2 border-t border-white/10 flex items-center gap-2 text-sm text-slate-300">
							<CheckCircle size={12} className="text-emerald-400" />
							<span>Valid JSON response</span>
							<button
								type="button"
								onClick={() => navigator.clipboard.writeText(result)}
								className="ml-auto text-amber-400 hover:text-amber-300"
							>
								Copy
							</button>
						</div>
					)}
				</div>
			</div>
		</div>
	);
}
