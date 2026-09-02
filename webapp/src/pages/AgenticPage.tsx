import { Bot, CheckCircle, Code2, Download, Layers, Loader2, Send, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface AgenticResult {
	success: boolean;
	output?: string;
	error?: string;
	data?: {
		steps: number;
		entity_count: number;
		plan: Array<{ source: string; code: string }>;
	};
}

interface DepotFile {
	name: string;
}

const EXAMPLES = [
	"Create a rectangular floor plan 10m x 8m with 4 equal rooms, add aligned dimensions on all sides",
	"Create a circle with radius 50mm and add a radial dimension",
	"Add text labels 'Room A', 'Room B', 'Room C' at positions (10,40), (60,40), (35,10) with height 150",
	"Create a grid of 1m squares covering 10m x 10m area",
];

export default function AgenticPage() {
	const [goal, setGoal] = useState("");
	const [file, setFile] = useState("");
	const [files, setFiles] = useState<DepotFile[]>([]);
	const [running, setRunning] = useState(false);
	const [result, setResult] = useState<AgenticResult | null>(null);
	const [error, setError] = useState("");
	const [history, setHistory] = useState<Array<{ goal: string; output: string }>>([]);
	const [qcadOk, setQcadOk] = useState(false);

	useEffect(() => {
		fetch(API_BASE + "/api/v1/status")
			.then((r) => r.json())
			.then((j) => {
				setQcadOk(j.qcad_pro?.installed ?? false);
			})
			.catch(() => {});
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

	const execute = async () => {
		if (!goal.trim()) return;
		setRunning(true);
		setError("");
		setResult(null);
		try {
			const r = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					tool: "plan_agentic",
					arguments: { goal: goal.trim(), file_name: file },
				}),
			});
			const j: AgenticResult = await r.json();
			if (j.success) {
				setResult(j);
				setHistory((prev) => [{ goal: goal.trim(), output: j.output || "" }, ...prev.slice(0, 9)]);
			} else {
				setError(j.error || "Agentic execution failed");
			}
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setRunning(false);
		}
	};

	return (
		<div className="max-w-5xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Bot className="text-amber-400" /> AI CAD Agent
			</h1>
			<p className="text-sm text-slate-300">
				Describe a CAD operation in natural language. The agent generates and executes ECMAScript via QCAD Pro.{" "}
				{!qcadOk && <span className="text-red-400">QCAD Pro not detected — install it for full capabilities.</span>}
			</p>

			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				{/* Input panel */}
				<div className="lg:col-span-2 bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-3">
					<textarea
						value={goal}
						onChange={(e) => setGoal(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter" && e.ctrlKey) execute();
						}}
						placeholder="Describe your CAD goal — e.g. 'Create a floor plan with 4 rooms, each 5m x 4m, with doors on the south wall, and add dimensions...'"
						rows={4}
						className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 resize-none"
					/>

					<div className="flex items-center gap-2 flex-wrap">
						{files.length > 0 && (
							<select
								value={file}
								onChange={(e) => setFile(e.target.value)}
								className="bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-sm text-slate-300 focus:outline-none focus:border-amber-500"
							>
								<option value="">New document</option>
								{files.map((f) => (
									<option key={f.name} value={f.name}>
										{f.name}
									</option>
								))}
							</select>
						)}

						<button
							type="button"
							onClick={execute}
							disabled={!goal.trim() || running}
							className="flex items-center gap-2 px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
						>
							{running ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
							{running ? "Executing..." : "Execute"}
						</button>
						<span className="text-xs text-slate-500 ml-auto">Ctrl+Enter to run</span>
					</div>

					{error && (
						<div className="p-3 rounded-xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
							<XCircle size={14} /> {error}
						</div>
					)}
				</div>

				{/* Examples + History */}
				<div className="space-y-4">
					<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
						<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Quick Examples</h3>
						{EXAMPLES.map((ex, i) => (
							<button
								type="button"
								// biome-ignore lint/suspicious/noArrayIndexKey: static list
								key={i}
								onClick={() => setGoal(ex)}
								className="w-full text-left p-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 transition-all line-clamp-2"
							>
								{ex}
							</button>
						))}
					</div>

					{history.length > 0 && (
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
							<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Recent</h3>
							{history.map((h, i) => (
								<button
									type="button"
									// biome-ignore lint/suspicious/noArrayIndexKey: replay history
									key={i}
									onClick={() => setGoal(h.goal)}
									className="w-full text-left p-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-400 transition-all truncate"
								>
									{h.goal}
								</button>
							))}
						</div>
					)}
				</div>
			</div>

			{/* Results */}
			{result && (
				<div className="space-y-4">
					<div className="grid grid-cols-4 gap-3">
						<div className="bg-[#1e1e26] border border-emerald-500/20 rounded-2xl p-4 text-center">
							<CheckCircle size={20} className="mx-auto mb-1 text-emerald-400" />
							<p className="text-2xl font-bold text-white">{result.data?.steps ?? 1}</p>
							<p className="text-xs text-slate-400">Steps Executed</p>
						</div>
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 text-center">
							<Layers size={20} className="mx-auto mb-1 text-amber-400" />
							<p className="text-2xl font-bold text-white">{result.data?.entity_count ?? "—"}</p>
							<p className="text-xs text-slate-400">Entities Created</p>
						</div>
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 text-center">
							<Code2 size={20} className="mx-auto mb-1 text-amber-400" />
							<p className="text-xs text-slate-400 mt-1">Generated Script</p>
							<p className="text-sm text-slate-300 mt-1">{result.data?.plan?.[0]?.source ?? "ai"} &rarr; QCAD Pro</p>
						</div>
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 text-center flex flex-col items-center justify-center">
							{result.output ? (
								<a
									href={`/api/v1/download/${result.output}`}
									className="flex items-center gap-1.5 px-3 py-2 bg-amber-600 hover:bg-amber-700 rounded-xl text-white text-sm font-bold"
								>
									<Download size={14} /> {result.output}
								</a>
							) : (
								<span className="text-slate-400 text-sm">No output file</span>
							)}
						</div>
					</div>

					{result.data?.plan?.map((step, i) => (
						<div
							// biome-ignore lint/suspicious/noArrayIndexKey: plan steps
							key={i}
							className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden"
						>
							<div className="px-4 py-2 bg-white/5 border-b border-white/10 flex items-center gap-2">
								<Code2 size={14} className="text-amber-400" />
								<span className="text-sm font-bold text-slate-300">
									Step {i + 1} — {step.source}
								</span>
							</div>
							<pre className="p-4 text-xs text-slate-300 font-mono overflow-x-auto max-h-64 overflow-y-auto">
								{step.code}
							</pre>
						</div>
					))}
				</div>
			)}

			{!result && !running && !error && (
				<div className="text-center py-12 text-slate-400">
					<Bot size={48} className="mx-auto mb-4 opacity-30" />
					<p>Describe a CAD goal above. The agent will generate and execute QCAD ECMAScript.</p>
				</div>
			)}
		</div>
	);
}
