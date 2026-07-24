import { AnimatePresence, motion } from "framer-motion";
import {
	AlertTriangle,
	ArrowLeft,
	ArrowRight,
	Box,
	ChevronRight,
	Code2,
	Cpu,
	Download,
	Eye,
	ExternalLink,
	FileText,
	GitBranch,
	Loader2,
	MessageSquareText,
	Ruler,
	Send,
	Wand2,
} from "lucide-react";
import { useCallback, useState } from "react";
import StlViewer from "../components/StlViewer";
import { API_BASE } from "../lib/api";

interface WallSegment {
	x1: number;
	y1: number;
	x2: number;
	y2: number;
	length_mm: number;
	angle_deg: number;
	layer: string;
}

interface AnalyseData {
	rooms: { name: string; area_m2: number }[];
	doors_windows: { type: string; width: number; height: number }[];
}

interface PipelineState {
	dxf: string | null;
	dxf_entities: number;
	svg: string | null;
	stl: string | null;
	stl_vertices: number;
	analyse: AnalyseData | null;
	wall_data: WallSegment[];
	wall_data_json: string | null;
	error: string | null;
}

const STEPS = [
	{ id: 1, label: "Describe", icon: MessageSquareText },
	{ id: 2, label: "View", icon: Eye },
	{ id: 3, label: "Analyse", icon: Ruler },
	{ id: 4, label: "Extrude", icon: Box },
	{ id: 5, label: "Pipeline", icon: GitBranch },
];

const MODELS = [
	{ value: "gemma3:1b", label: "Gemma 3 1B (fast)" },
	{ value: "llama3.2:3b", label: "Llama 3.2 3B" },
	{ value: "gemma3:12b", label: "Gemma 3 12B (best)" },
];

const PRESETS = [
	{
		label: "Studio",
		goal: "Create an open-plan studio apartment 6m x 5m with a kitchenette corner, bathroom 2m x 1.5m, entrance hallway, and a balcony 3m x 1.5m on the south wall. Add dimensions and room labels.",
	},
	{
		label: "Office",
		goal: "Create an office floor plan 20m x 15m with 6 private offices 3m x 3m along the north wall, an open-plan workspace, two meeting rooms 4m x 4m, kitchen, and two bathrooms.",
	},
	{
		label: "Cafe",
		goal: "Create a cafe layout 8m x 10m with a serving counter 4m wide, 6 tables for 4 people, 4 tables for 2 people, a bar area with 8 stools, and a small outdoor terrace 3m x 8m.",
	},
];

export default function PipelinePage() {
	const [step, setStep] = useState(1);
	const [goal, setGoal] = useState("");
	const [model, setModel] = useState("gemma3:1b");
	const [wallHeight, setWallHeight] = useState(3.0);
	const [wallThickness, setWallThickness] = useState(0.3);
	const [running, setRunning] = useState(false);
	const [runningOp, setRunningOp] = useState<string | null>(null);
	const [state, setState] = useState<PipelineState>({
		dxf: null,
		dxf_entities: 0,
		svg: null,
		stl: null,
		stl_vertices: 0,
		analyse: null,
		wall_data: [],
		wall_data_json: null,
		error: null,
	});

	const callTool = useCallback(
		async (tool: string, args: Record<string, unknown>) => {
			setRunningOp(tool);
			const r = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ tool, arguments: args }),
			});
			const data = await r.json();
			setRunningOp(null);
			return data;
		},
		[],
	);

	const handleGenerate = async () => {
		if (!goal.trim()) return;
		setRunning(true);
		setState((p) => ({ ...p, error: null }));
		try {
			const ts = Date.now();
			const dxfName = `pipeline_${ts}.dxf`;
			const agentic = await callTool("plan_agentic", {
				goal: goal.trim(),
			});
			if (!agentic.success) throw new Error(agentic.error || "Generation failed");
			setState((p) => ({
				...p,
				dxf: agentic.output,
				dxf_entities: agentic.data?.entity_count ?? 0,
				svg: null,
				stl: null,
				stl_vertices: 0,
				analyse: null,
				wall_data: [],
				wall_data_json: null,
			}));
			setStep(2);
		} catch (e: unknown) {
			setState((p) => ({
				...p,
				error: e instanceof Error ? e.message : String(e),
			}));
		} finally {
			setRunning(false);
		}
	};

	const handleAnalyse = async () => {
		if (!state.dxf) return;
		setRunning(true);
		try {
			const svgRes = await callTool("plan_to_svg", {
				file_name: state.dxf,
				output_name: `pipeline_${Date.now()}.svg`,
			});
			setState((p) => ({
				...p,
				svg: svgRes.success ? svgRes.output : null,
			}));

			const analyseRes = await callTool("plan_analyse", {
				file_name: state.dxf,
			});
			if (analyseRes.success) {
				setState((p) => ({
					...p,
					analyse: analyseRes.data ?? null,
				}));
			}
			setStep(3);
		} catch (e: unknown) {
			setState((p) => ({
				...p,
				error: e instanceof Error ? e.message : String(e),
			}));
		} finally {
			setRunning(false);
		}
	};

	const handleExtrude = async () => {
		if (!state.dxf) return;
		setRunning(true);
		try {
			const ts = Date.now();
			const stlRes = await callTool("plan_extrude", {
				file_name: state.dxf,
				output_name: `pipeline_${ts}.stl`,
				wall_height: wallHeight,
				wall_thickness: wallThickness,
			});
			if (stlRes.success) {
				setState((p) => ({
					...p,
					stl: stlRes.output,
					stl_vertices: stlRes.data?.vertices ?? 0,
				}));
			}
			setStep(4);
		} catch (e: unknown) {
			setState((p) => ({
				...p,
				error: e instanceof Error ? e.message : String(e),
			}));
		} finally {
			setRunning(false);
		}
	};

	const handlePipeline = async () => {
		if (!state.dxf) return;
		setRunning(true);
		try {
			const wallRes = await callTool("plan_wall_data", {
				file_name: state.dxf,
			});
			if (wallRes.success) {
				const walls: WallSegment[] = wallRes.data?.walls ?? [];
				setState((p) => ({
					...p,
					wall_data: walls,
					wall_data_json: JSON.stringify(walls, null, 2),
				}));
			}
			setStep(5);
		} catch (e: unknown) {
			setState((p) => ({
				...p,
				error: e instanceof Error ? e.message : String(e),
			}));
		} finally {
			setRunning(false);
		}
	};

	const freecadCallSequence = [
		{ tool: "bim_create_wall", desc: "Create walls from segments" },
		{ tool: "bim_create_slab", desc: "Create floor slab" },
		{ tool: "bim_create_roof", desc: "Create roof" },
		{ tool: "bim_export_ifc", desc: "Export as IFC" },
	];

	return (
		<div className="max-w-6xl mx-auto space-y-6 pb-12">
			{/* Header */}
			<div className="flex items-center gap-3">
				<div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center">
					<GitBranch size={20} className="text-white" />
				</div>
				<div>
					<h1 className="text-2xl font-bold text-white">Pipeline Wizard</h1>
					<p className="text-sm text-slate-400">
						NL plan &rarr; DXF &rarr; Analyse &rarr; 3D &rarr; FreeCAD BIM
					</p>
				</div>
			</div>

			{/* Step Tabs */}
			<div className="flex items-center gap-1 bg-[#1e1e26] border border-white/10 rounded-2xl p-1.5">
				{STEPS.map((s, i) => (
					<button
						type="button"
						key={s.id}
						onClick={() => {
							if (!running) setStep(s.id);
						}}
						disabled={running}
						className={`flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
							step === s.id
								? "bg-amber-600 text-white shadow-lg shadow-amber-600/20"
								: step > s.id
									? "text-emerald-400 hover:bg-white/5"
									: "text-slate-500 hover:text-slate-300 hover:bg-white/5"
						}`}
					>
						<s.icon size={16} />
						<span className="hidden sm:inline">{s.label}</span>
						{i < STEPS.length - 1 && (
							<ChevronRight size={14} className="hidden sm:inline opacity-40" />
						)}
					</button>
				))}
			</div>

			{/* Step Content */}
			<AnimatePresence mode="wait">
				<motion.div
					key={step}
					initial={{ opacity: 0, y: 12 }}
					animate={{ opacity: 1, y: 0 }}
					exit={{ opacity: 0, y: -12 }}
					transition={{ duration: 0.2 }}
				>
					{/* Step 1: Describe */}
					{step === 1 && (
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
							<div className="flex items-center gap-2 text-amber-400">
								<MessageSquareText size={18} />
								<h2 className="text-lg font-bold text-white">
									Describe Your Plan
								</h2>
							</div>
							<p className="text-sm text-slate-400">
								Describe a floor plan in natural language. The AI will generate
								a parametric DXF drawing.
							</p>
							<div className="space-y-2">
								<textarea
									value={goal}
									onChange={(e) => setGoal(e.target.value)}
									onKeyDown={(e) => {
										if (e.key === "Enter" && e.ctrlKey) handleGenerate();
									}}
									placeholder="Describe your building — e.g. 'Create a 3-story apartment building, 2 units per floor...'"
									rows={4}
									className="w-full bg-black/40 border border-amber-500/20 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 resize-none"
									disabled={running}
								/>
							</div>
							<div className="flex items-center gap-3">
								<div className="flex items-center gap-2">
									<Cpu size={14} className="text-slate-500" />
									<select
										value={model}
										onChange={(e) => setModel(e.target.value)}
										className="bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-amber-500"
									>
										{MODELS.map((m) => (
											<option key={m.value} value={m.value}>
												{m.label}
											</option>
										))}
									</select>
								</div>
								<div className="flex-1" />
								<button
									type="button"
									onClick={handleGenerate}
									disabled={!goal.trim() || running}
									className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
								>
									{running && runningOp === "plan_agentic" ? (
										<Loader2 size={14} className="animate-spin" />
									) : (
										<Wand2 size={14} />
									)}
									Generate Plan
								</button>
							</div>
							<div className="flex flex-wrap gap-2">
								<span className="text-xs text-slate-500 self-center mr-1">
									Try:
								</span>
								{PRESETS.map((p) => (
									<button
										type="button"
										key={p.label}
										onClick={() => setGoal(p.goal)}
										disabled={running}
										className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 border border-white/5"
									>
										{p.label}
									</button>
								))}
							</div>
						</div>
					)}

					{/* Step 2: View */}
					{step === 2 && (
						<div className="space-y-4">
							<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
								<div className="px-4 py-3 bg-white/5 border-b border-white/10 flex items-center justify-between">
									<div className="flex items-center gap-2">
										<Eye size={14} className="text-amber-400" />
										<span className="text-sm font-bold text-slate-300">
											2D Floor Plan
										</span>
										{state.dxf_entities > 0 && (
											<span className="text-xs text-slate-500">
												({state.dxf_entities} entities)
											</span>
										)}
									</div>
									<div className="flex items-center gap-2">
										{state.svg && (
											<a
												href={`/api/v1/download/${state.svg}`}
												className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 text-sm"
											>
												<Download size={12} /> SVG
											</a>
										)}
										{state.dxf && (
											<a
												href={`/api/v1/download/${state.dxf}`}
												className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-sm"
											>
												<Download size={12} /> DXF
											</a>
										)}
									</div>
								</div>
								{state.svg ? (
									<div className="p-4 bg-[#18181c] flex items-center justify-center min-h-[300px]">
										<img
											src={`/api/v1/download/${state.svg}`}
											alt="Floor plan"
											className="max-w-full max-h-[500px] object-contain"
										/>
									</div>
								) : (
									<div className="flex items-center justify-center h-[300px] text-slate-500 text-sm">
										<Loader2
											size={20}
											className="animate-spin mr-2 text-amber-400"
										/>
										Generating preview...
									</div>
								)}
							</div>
							<div className="flex justify-end">
								<button
									type="button"
									onClick={() => {
										setStep(1);
									}}
									className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-sm mr-2"
								>
									<ArrowLeft size={14} /> Back
								</button>
								<button
									type="button"
									onClick={handleAnalyse}
									disabled={running}
									className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
								>
									{running ? (
										<Loader2 size={14} className="animate-spin" />
									) : (
										<Ruler size={14} />
									)}
									Analyse
								</button>
							</div>
						</div>
					)}

					{/* Step 3: Analyse */}
					{step === 3 && (
						<div className="space-y-4">
							<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
								<div className="flex items-center gap-2 text-amber-400">
									<Ruler size={18} />
									<h2 className="text-lg font-bold text-white">
										Room Analysis
									</h2>
								</div>
								{state.analyse ? (
									<div className="space-y-6">
										{state.analyse.rooms.length > 0 && (
											<div>
												<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">
													Rooms
												</h3>
												<table className="w-full text-sm">
													<thead>
														<tr className="text-slate-500 border-b border-white/10">
															<th className="text-left py-2 px-2">Room</th>
															<th className="text-right py-2 px-2">
																Area (m&sup2;)
															</th>
														</tr>
													</thead>
													<tbody>
														{state.analyse.rooms.map((r, i) => (
															<tr
																key={i}
																className="border-b border-white/5"
															>
																<td className="py-2 px-2 text-slate-300">
																	{r.name}
																</td>
																<td className="py-2 px-2 text-right text-slate-300">
																	{r.area_m2.toFixed(1)}
																</td>
															</tr>
														))}
													</tbody>
												</table>
											</div>
										)}
										{state.analyse.doors_windows.length > 0 && (
											<div>
												<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">
													Doors &amp; Windows
												</h3>
												<table className="w-full text-sm">
													<thead>
														<tr className="text-slate-500 border-b border-white/10">
															<th className="text-left py-2 px-2">Type</th>
															<th className="text-right py-2 px-2">
																Width (mm)
															</th>
															<th className="text-right py-2 px-2">
																Height (mm)
															</th>
														</tr>
													</thead>
													<tbody>
														{state.analyse.doors_windows.map((d, i) => (
															<tr
																key={i}
																className="border-b border-white/5"
															>
																<td className="py-2 px-2 capitalize text-slate-300">
																	{d.type}
																</td>
																<td className="py-2 px-2 text-right text-slate-300">
																	{d.width}
																</td>
																<td className="py-2 px-2 text-right text-slate-300">
																	{d.height}
																</td>
															</tr>
														))}
													</tbody>
												</table>
											</div>
										)}
									</div>
								) : (
									<div className="flex items-center justify-center h-[200px] text-slate-500 text-sm">
										{running ? (
											<>
												<Loader2
													size={20}
													className="animate-spin mr-2 text-amber-400"
												/>
												Analysing plan...
											</>
										) : (
											"Click Analyse to detect rooms and openings"
										)}
									</div>
								)}
							</div>
							<div className="flex justify-end">
								<button
									type="button"
									onClick={() => setStep(2)}
									className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-sm mr-2"
								>
									<ArrowLeft size={14} /> Back
								</button>
								<button
									type="button"
									onClick={handleExtrude}
									disabled={running}
									className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
								>
									{running ? (
										<Loader2 size={14} className="animate-spin" />
									) : (
										<Box size={14} />
									)}
									Extrude to 3D
								</button>
							</div>
						</div>
					)}

					{/* Step 4: Extrude */}
					{step === 4 && (
						<div className="space-y-4">
							<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
								<div className="flex items-center gap-2 text-amber-400">
									<Box size={18} />
									<h2 className="text-lg font-bold text-white">
										3D Extrusion
									</h2>
								</div>
								<div className="grid grid-cols-2 gap-4">
									<div className="space-y-1.5">
										<label className="text-xs text-slate-400 font-medium">
											Wall Height (m)
										</label>
										<input
											type="number"
											value={wallHeight}
											onChange={(e) =>
												setWallHeight(Number(e.target.value))
											}
											step={0.1}
											min={1}
											max={10}
											className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
										/>
									</div>
									<div className="space-y-1.5">
										<label className="text-xs text-slate-400 font-medium">
											Wall Thickness (m)
										</label>
										<input
											type="number"
											value={wallThickness}
											onChange={(e) =>
												setWallThickness(Number(e.target.value))
											}
											step={0.05}
											min={0.05}
											max={1}
											className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-amber-500"
										/>
									</div>
								</div>
								<button
									type="button"
									onClick={handleExtrude}
									disabled={running || !state.dxf}
									className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold w-fit"
								>
									{running && runningOp === "plan_extrude" ? (
										<Loader2 size={14} className="animate-spin" />
									) : (
										<Wand2 size={14} />
									)}
									Generate STL
								</button>
							</div>
							{state.stl && (
								<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
									<div className="px-4 py-3 bg-white/5 border-b border-white/10 flex items-center justify-between">
										<div className="flex items-center gap-2">
											<Box size={14} className="text-amber-400" />
											<span className="text-sm font-bold text-slate-300">
												3D Preview
											</span>
											<span className="text-xs text-slate-500">
												({state.stl_vertices} vertices)
											</span>
										</div>
										<a
											href={`/api/v1/download/${state.stl}`}
											className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 text-sm"
										>
											<Download size={12} /> Download STL
										</a>
									</div>
									<div className="h-[450px]">
										<StlViewer
											url={`/api/v1/download/${state.stl}`}
										/>
									</div>
								</div>
							)}
							<div className="flex justify-end">
								<button
									type="button"
									onClick={() => setStep(3)}
									className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-sm mr-2"
								>
									<ArrowLeft size={14} /> Back
								</button>
								<button
									type="button"
									onClick={handlePipeline}
									disabled={running}
									className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
								>
									{running ? (
										<Loader2 size={14} className="animate-spin" />
									) : (
										<GitBranch size={14} />
									)}
									Pipeline
								</button>
							</div>
						</div>
					)}

					{/* Step 5: Pipeline */}
					{step === 5 && (
						<div className="space-y-4">
							<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
								<div className="flex items-center gap-2 text-amber-400">
									<GitBranch size={18} />
									<h2 className="text-lg font-bold text-white">
										FreeCAD BIM Pipeline
									</h2>
								</div>
								<p className="text-sm text-slate-400">
									Wall data extracted from the DXF plan is ready for FreeCAD
									BIM tools. Use the call sequence below to reconstruct the
									building in FreeCAD.
								</p>
								{state.wall_data.length > 0 && (
									<div className="bg-black/40 border border-white/10 rounded-xl p-4 space-y-2">
										<div className="flex items-center justify-between">
											<span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
												Wall Segments ({state.wall_data.length})
											</span>
											{state.wall_data_json && (
												<a
													href={`data:text/json;charset=utf-8,${encodeURIComponent(state.wall_data_json)}`}
													download="wall_data.json"
													className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300"
												>
													<FileText size={12} /> Download JSON
												</a>
											)}
										</div>
										<div className="max-h-[240px] overflow-y-auto">
											<table className="w-full text-xs">
												<thead>
													<tr className="text-slate-500 border-b border-white/10">
														<th className="text-left py-1.5 px-1">#</th>
														<th className="text-left py-1.5 px-1">From</th>
														<th className="text-left py-1.5 px-1">To</th>
														<th className="text-right py-1.5 px-1">
															Length (mm)
														</th>
														<th className="text-right py-1.5 px-1">
															Angle
														</th>
														<th className="text-left py-1.5 px-1">Layer</th>
													</tr>
												</thead>
												<tbody>
													{state.wall_data.map((w, i) => (
														<tr
															key={i}
															className="border-b border-white/5 hover:bg-white/5"
														>
															<td className="py-1.5 px-1 text-slate-500 font-mono">
																{i}
															</td>
															<td className="py-1.5 px-1 text-slate-300 font-mono">
																{w.x1},{w.y1}
															</td>
															<td className="py-1.5 px-1 text-slate-300 font-mono">
																{w.x2},{w.y2}
															</td>
															<td className="py-1.5 px-1 text-right text-slate-300 font-mono">
																{w.length_mm.toFixed(0)}
															</td>
															<td className="py-1.5 px-1 text-right text-slate-300 font-mono">
																{w.angle_deg.toFixed(1)}&deg;
															</td>
															<td className="py-1.5 px-1 text-slate-400">
																{w.layer}
															</td>
														</tr>
													))}
												</tbody>
											</table>
										</div>
									</div>
								)}
							</div>

							{/* FreeCAD BIM Live Panel */}
							<div className="bg-[#1e1e26] border border-amber-500/20 rounded-2xl p-6 space-y-4">
								<div className="flex items-center gap-2 text-amber-400">
									<Send size={18} />
									<h2 className="text-lg font-bold text-white">
										Send to FreeCAD
									</h2>
								</div>
								<p className="text-sm text-slate-400">
									Extract wall segments as BIM-ready JSON and generate
									freecad-mcp tool calls:
								</p>
								{state.wall_data.length > 0 && (
									<>
										<div className="bg-black/40 border border-white/10 rounded-xl p-3 max-h-[200px] overflow-y-auto">
											<table className="w-full text-xs">
												<thead>
													<tr className="text-slate-400 border-b border-white/10">
														<th className="text-left py-1 pr-2">Layer</th>
														<th className="text-left py-1 pr-2">Length</th>
														<th className="text-left py-1 pr-2">Angle</th>
														<th className="text-left py-1 pr-2">From</th>
														<th className="text-left py-1 pr-2">To</th>
													</tr>
												</thead>
												<tbody>
													{state.wall_data.map((w, i) => (
														<tr key={i} className="border-b border-white/5 text-slate-300">
															<td className="py-1 pr-2">{w.layer}</td>
															<td className="py-1 pr-2">{(w.length_mm / 1000).toFixed(2)}m</td>
															<td className="py-1 pr-2">{w.angle_deg.toFixed(0)}°</td>
															<td className="py-1 pr-2 font-mono">{w.x1},{w.y1}</td>
															<td className="py-1 pr-2 font-mono">{w.x2},{w.y2}</td>
														</tr>
													))}
												</tbody>
											</table>
										</div>
										<button type="button"
											onClick={() => {
												const calls = state.wall_data.map((w) =>
													`bim_create_wall(x1=${w.x1}, y1=${w.y1}, x2=${w.x2}, y2=${w.y2}, height=3.0, thickness=0.3)`);
												navigator.clipboard.writeText(calls.join("\n"));
											}}
											className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold w-fit">
											<Code2 size={14} /> Copy FreeCAD tool calls
										</button>
									</>
								)}
								{state.wall_data.length === 0 && state.dxf && (
									<button type="button"
										onClick={() => handlePipeline()}
										className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold w-fit">
										<Code2 size={14} /> Extract Wall Data
									</button>
								)}
								{!state.dxf && (
									<div className="bg-amber-950/30 border border-amber-500/10 rounded-xl p-4 text-sm text-slate-300 space-y-2">
										<div className="flex items-center gap-2 text-amber-300">
											<ExternalLink size={14} />
											<span className="font-bold">freecad-mcp</span>
										</div>
										<p>Complete steps 1–4 first to generate a DXF with wall data.</p>
									</div>
								)}
							</div>
							<div className="flex justify-end">
								<button
									type="button"
									onClick={() => setStep(4)}
									className="flex items-center gap-2 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-sm mr-2"
								>
									<ArrowLeft size={14} /> Back
								</button>
								<button
									type="button"
									onClick={() => {
										setStep(1);
										setGoal("");
										setState({
											dxf: null,
											dxf_entities: 0,
											svg: null,
											stl: null,
											stl_vertices: 0,
											analyse: null,
											wall_data: [],
											wall_data_json: null,
											error: null,
										});
									}}
									className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white text-sm font-bold"
								>
									<ArrowRight size={14} /> New Pipeline
								</button>
							</div>
						</div>
					)}
				</motion.div>
			</AnimatePresence>

			{/* Error */}
			{state.error && (
				<div className="flex items-start gap-3 p-4 rounded-2xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm">
					<AlertTriangle size={16} className="shrink-0 mt-0.5" />
					<span>{state.error}</span>
				</div>
			)}

			{/* Global running indicator */}
			{runningOp && (
				<div className="flex items-center gap-2 text-xs text-amber-400">
					<Loader2 size={12} className="animate-spin" />
					Running: {runningOp}
				</div>
			)}
		</div>
	);
}
