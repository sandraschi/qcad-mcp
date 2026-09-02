import { BarChart3, Box, CheckCircle, Download, FileText, Loader2, Play, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface PlanInfoData {
	entity_total: number;
	layer_count: number;
	block_count: number;
	dxf_version: string;
}
interface PlanAnalyseData {
	rooms: unknown[];
	wall_length_m: number;
}
interface StlResult {
	stl: string;
	vertices: number;
}

interface BatchResult {
	success: boolean;
	file: string;
	data?: unknown;
	error?: string;
	output?: string;
}

export default function BatchPage() {
	const [files, setFiles] = useState<{ name: string }[]>([]);
	const [tool, setTool] = useState("plan_info");
	const [results, setResults] = useState<BatchResult[] | null>(null);
	const [running, setRunning] = useState(false);
	const [error, setError] = useState("");
	const [stlResults, setStlResults] = useState<StlResult[]>([]);

	useEffect(() => {
		fetch(API_BASE + "/api/v1/files")
			.then((r) => r.json())
			.then((j) => {
				const all = [...(j.uploads || []), ...(j.outputs || [])].filter((f: { name: string }) =>
					f.name.match(/\.(dxf|dwg)$/i),
				);
				setFiles(all);
			})
			.catch(() => {});
	}, []);

	const run = async () => {
		if (tool === "batch_extrude") {
			await runBatchExtrude();
			return;
		}
		setRunning(true);
		setError("");
		setResults(null);
		setStlResults([]);
		try {
			const r = await fetch(API_BASE + "/api/v1/batch", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ tool, args: {} }),
			});
			const j = await r.json();
			if (j.results) setResults(j.results);
			else setError(j.error || "Batch run failed");
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setRunning(false);
		}
	};

	const runBatchExtrude = async () => {
		setRunning(true);
		setError("");
		setResults(null);
		setStlResults([]);
		const dxfFiles = files.filter((f) => f.name.match(/\.dxf$/i));
		const out: StlResult[] = [];
		for (const f of dxfFiles) {
			try {
				const r = await fetch(API_BASE + "/api/v1/control/tool", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						tool: "plan_extrude",
						arguments: { file_name: f.name, wall_layers: ["Walls"], wall_height: 3.0, wall_thickness: 0.15 },
					}),
				});
				const j = await r.json();
				if (j.success) out.push({ stl: j.output, vertices: j.data?.vertices ?? 0 });
			} catch {}
		}
		setStlResults(out);
		setRunning(false);
	};

	return (
		<div className="max-w-4xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Play className="text-amber-400" /> Batch Pipeline
			</h1>

			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-4">
				<div className="flex items-center gap-3">
					<span className="text-sm text-slate-400">Tool:</span>
					<select
						value={tool}
						onChange={(e) => setTool(e.target.value)}
						className="bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-amber-500"
					>
						<option value="plan_info">plan_info (metadata)</option>
						<option value="plan_analyse">plan_analyse (room detection)</option>
						<option value="batch_extrude">plan_extrude (STL batch)</option>
					</select>
					<span className="text-sm text-slate-500">
						{files.length} file{files.length !== 1 ? "s" : ""} in depot
					</span>
					<button
						type="button"
						onClick={run}
						disabled={running || files.length === 0}
						className="ml-auto flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
					>
						{running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
						{running ? "Running..." : `Run on ${files.length} files`}
					</button>
				</div>
				{error && <p className="text-red-400 text-sm">{error}</p>}
			</div>

			{/* Batch STL results */}
			{stlResults.length > 0 && (
				<div className="space-y-2">
					<p className="text-sm text-slate-400 flex items-center gap-2">
						<Box size={14} className="text-amber-400" /> {stlResults.length} STL files generated
					</p>
					<div className="grid grid-cols-2 md:grid-cols-4 gap-3">
						{stlResults.map((s, i) => (
							<div key={i} className="bg-[#1e1e26] border border-white/10 rounded-xl p-3 text-center">
								<p className="text-xs text-slate-300 truncate">{s.stl}</p>
								<p className="text-xs text-slate-500">{s.vertices} vertices</p>
								<a
									href={`/api/v1/download/${s.stl}`}
									className="inline-flex items-center gap-1 mt-2 text-amber-400 text-xs hover:underline"
								>
									<Download size={12} /> STL
								</a>
							</div>
						))}
					</div>
				</div>
			)}

			{/* Batch analysis results */}
			{results && (
				<div className="space-y-2">
					<p className="text-sm text-slate-400">
						{results.filter((r) => r.success).length}/{results.length} succeeded
					</p>
					{results.map((r) => (
						<div
							key={r.file}
							className={`bg-[#1e1e26] border rounded-xl p-3 ${r.success ? "border-emerald-500/20" : "border-red-500/20"}`}
						>
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-2">
									{r.success ? (
										<CheckCircle size={16} className="text-emerald-400" />
									) : (
										<XCircle size={16} className="text-red-400" />
									)}
									<span className="text-sm font-bold text-white">{r.file}</span>
								</div>
								<span className="text-xs text-slate-500">{r.success ? "OK" : "Failed"}</span>
							</div>
							{r.success && tool === "plan_info" && (
								<div className="mt-2 text-xs text-slate-400 space-y-0.5">
									<span>
										Entities: {(r.data as PlanInfoData)?.entity_total ?? "?"} · Layers:{" "}
										{(r.data as PlanInfoData)?.layer_count ?? "?"} · Blocks:{" "}
										{(r.data as PlanInfoData)?.block_count ?? "?"} · DXF: {(r.data as PlanInfoData)?.dxf_version ?? "?"}
									</span>
								</div>
							)}
							{r.success && tool === "plan_analyse" && (
								<div className="mt-2 text-xs text-slate-400 space-y-0.5">
									<span>
										Rooms: {(r.data as PlanAnalyseData)?.rooms?.length ?? "0"} · Wall length: {(() => {
											const wl = (r.data as PlanAnalyseData)?.wall_length_m;
											return wl != null ? `${wl.toFixed(1)}m` : "?";
										})()}
									</span>
								</div>
							)}
							{r.error && <p className="mt-1 text-xs text-red-400">{r.error}</p>}
						</div>
					))}
				</div>
			)}

			{!running && !results && stlResults.length === 0 && (
				<div className="text-center py-12 text-slate-600">
					<Play size={48} className="mx-auto mb-4 opacity-30" />
					<p>Select a tool and run it on all DXF/DWG files in the depot.</p>
				</div>
			)}
		</div>
	);
}
