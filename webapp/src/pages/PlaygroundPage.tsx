import { AlertTriangle, CheckCircle, Code2, Loader2, Play, Terminal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

const TOOLS = [
	"plan_info",
	"plan_to_svg",
	"plan_extrude",
	"plan_export",
	"plan_analyse",
	"plan_measure",
	"plan_create",
	"plan_depot",
	"plan_convert",
	"plan_modify",
	"plan_dimension",
	"plan_text",
	"plan_hatch",
	"plan_block_insert",
	"plan_array",
	"plan_wall_data",
	"plan_beam_analysis",
	"plan_blocks",
	"plan_blocks_download",
	"plan_scripts_search",
	"plan_scripts_download",
	"plan_script",
	"plan_render",
	"plan_exec",
	"qcad_status",
];

const ARG_TEMPLATES: Record<string, string> = {
	plan_info: JSON.stringify({ file_name: "studio_apt.dxf" }, null, 2),
	plan_to_svg: JSON.stringify({ file_name: "studio_apt.dxf", output_name: "preview.svg" }, null, 2),
	plan_extrude: JSON.stringify(
		{
			file_name: "studio_apt.dxf",
			output_name: "extruded.stl",
			wall_height: 3.0,
			wall_thickness: 0.15,
			wall_layers: ["Walls"],
		},
		null,
		2,
	),
	plan_export: JSON.stringify({ file_name: "studio_apt.dxf", format: "svg", output_name: "export.svg" }, null, 2),
	plan_analyse: JSON.stringify({ file_name: "studio_apt.dxf" }, null, 2),
	plan_blocks: JSON.stringify({ query: "door", limit: 5 }, null, 2),
	plan_depot: "{}",
	qcad_status: "{}",
	plan_beam_analysis: JSON.stringify(
		{
			beams: [{ x1: 0, y1: 0, x2: 4000, y2: 0, label: "B1" }],
			supports: [
				{ x: 0, y: 0, type: "pinned" },
				{ x: 4000, y: 0, type: "roller" },
			],
			loads: [{ x: 2000, y: 0, value: -5000 }],
		},
		null,
		2,
	),
};

export default function PlaygroundPage() {
	const [tool, setTool] = useState("plan_info");
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
						<label className="text-sm text-slate-400">Tool</label>
						<select
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
							<label className="text-sm text-slate-400">Arguments (JSON)</label>
							{depotFiles.length > 0 && (
								<div className="flex items-center gap-1">
									<span className="text-xs text-slate-500">Files:</span>
									<select
										onChange={(e) => {
											if (e.target.value) insertFileName(e.target.value);
											e.target.value = "";
										}}
										className="bg-black/40 border border-white/10 rounded text-[10px] px-2 py-1 text-slate-300 max-w-[140px]"
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
							value={argsText}
							onChange={(e) => setArgsText(e.target.value)}
							rows={12}
							className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-xs font-mono text-emerald-300 placeholder-slate-600 focus:outline-none focus:border-amber-500 resize-none"
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
							<div className="flex items-start gap-2 text-red-400 text-xs bg-red-950/30 border border-red-500/20 rounded-xl p-3">
								<AlertTriangle size={14} className="shrink-0 mt-0.5" />
								<span>{error}</span>
							</div>
						)}
					</div>
				</div>
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
					<div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
						<Code2 size={14} className="text-amber-400" />
						<span className="text-sm font-bold text-slate-400 uppercase tracking-wider">Response</span>
						{result && <span className="text-xs text-slate-500 ml-auto">{result.length} bytes</span>}
					</div>
					<pre className="p-4 text-xs font-mono text-slate-300 overflow-auto max-h-[600px] whitespace-pre-wrap">
						{result || <span className="text-slate-600">Execute a tool to see the response here.</span>}
					</pre>
					{result && (
						<div className="px-4 py-2 border-t border-white/10 flex items-center gap-2 text-xs text-slate-500">
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
