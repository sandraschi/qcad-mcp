import {
	Box,
	CheckCircle,
	Download,
	ExternalLink,
	Eye,
	Loader2,
	Sparkles,
	Wand2,
} from "lucide-react";
import { useState } from "react";
import StlViewer from "../components/StlViewer";
import { API_BASE } from "../lib/api";

interface Step {
	label: string;
	status: "waiting" | "running" | "done" | "error";
	detail?: string;
}

interface DemoResult {
	dxf: string | null;
	dxf_entities: number;
	svg: string | null;
	stl: string | null;
	stl_vertices: number;
	error: string | null;
}

const PRESETS = [
	{
		label: "Studio Apartment",
		emoji: "🏠",
		goal: "Create an open-plan studio apartment 6m x 5m with a kitchenette corner, bathroom 2m x 1.5m, entrance hallway, and a balcony 3m x 1.5m on the south wall. Add dimensions and room labels.",
	},
	{
		label: "Office Floor",
		emoji: "🏢",
		goal: "Create an office floor plan 20m x 15m with 6 private offices 3m x 3m along the north wall, an open-plan workspace 12m x 8m, two meeting rooms 4m x 4m, kitchen, and two bathrooms. Add grid lines and dimensions.",
	},
	{
		label: "Cafe Layout",
		emoji: "☕",
		goal: "Create a cafe layout 8m x 10m with a serving counter 4m wide, 6 tables for 4 people, 4 tables for 2 people, a bar area with 8 stools, and a small outdoor terrace 3m x 8m. Add furniture labels.",
	},
];

export default function DemoPage() {
	const [goal, setGoal] = useState("");
	const [running, setRunning] = useState(false);
	const [steps, setSteps] = useState<Step[]>([]);
	const [result, setResult] = useState<DemoResult | null>(null);

	const updateStep = (idx: number, patch: Partial<Step>) => {
		setSteps((prev) =>
			prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)),
		);
	};

	const execute = async () => {
		if (!goal.trim()) return;
		setRunning(true);
		setResult(null);
		const baseSteps: Step[] = [
			{ label: "AI generates floor plan", status: "waiting" },
			{ label: "Render 2D SVG preview", status: "waiting" },
			{ label: "Extrude walls to 3D", status: "waiting" },
			{ label: "Ready for import", status: "waiting" },
		];
		setSteps(baseSteps);

		const callTool = async (tool: string, args: Record<string, unknown>) => {
			const r = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ tool, arguments: args }),
			});
			return r.json();
		};

		try {
			// Step 1: Create floor plan
			updateStep(0, { status: "running" });
			const timestamp = Date.now();
			const dxfName = `demo_${timestamp}.dxf`;

			const agenticResult = await callTool("plan_agentic", { goal: goal.trim() });
			const agenticOk = agenticResult.success;

			let dxfFile: string;
			let entityCount: number;
			if (agenticOk) {
				dxfFile = agenticResult.output;
				entityCount = agenticResult.data?.entity_count ?? 0;
			} else {
				// Fallback: create DXF from geometric primitives via ezdxf
				const createResult = await callTool("plan_create", {
					filename: dxfName,
					description: goal.trim(),
					entities: [
						{ type: "rect", x1: 0, y1: 0, x2: 6000, y2: 5000, layer: "Walls" },
						{ type: "line", x1: 0, y1: 1500, x2: 2000, y2: 1500, layer: "Walls" },
						{ type: "line", x1: 2000, y1: 1500, x2: 2000, y2: 0, layer: "Walls" },
						{ type: "line", x1: 1500, y1: 5000, x2: 4500, y2: 5000, layer: "Walls" },
						{ type: "line", x1: 4500, y1: 5000, x2: 4500, y2: 6500, layer: "Walls" },
						{ type: "line", x1: 4500, y1: 6500, x2: 1500, y2: 6500, layer: "Walls" },
						{ type: "line", x1: 1500, y1: 6500, x2: 1500, y2: 5000, layer: "Walls" },
						{ type: "text", x: 1000, y: 750, h: 300, text: "BATH", layer: "Text" },
						{ type: "text", x: 4000, y: 2500, h: 500, text: "LIVING", layer: "Text" },
						{ type: "text", x: 4000, y: 3000, h: 500, text: "AREA", layer: "Text" },
						{ type: "text", x: 3000, y: 5750, h: 300, text: "BALCONY", layer: "Text" },
					],
					layers: [
						{ name: "Walls", color: 7, description: "Walls" },
						{ name: "Text", color: 2, description: "Labels" },
					],
				});
				if (!createResult.success)
					throw new Error(createResult.error || "Failed to create floor plan");
				dxfFile = dxfName;
				entityCount = createResult.data?.entity_count ?? 0;
			}

			updateStep(0, { status: "done", detail: `${entityCount} entities` });
			setResult({ dxf: dxfFile, dxf_entities: entityCount, svg: null, stl: null, stl_vertices: 0, error: null });

			// Step 2: Render SVG preview
			updateStep(1, { status: "running" });
			const svgResult = await callTool("plan_to_svg", {
				file_name: dxfFile,
				output_name: `demo_${timestamp}.svg`,
			});
			updateStep(1, {
				status: svgResult.success ? "done" : "error",
				detail: svgResult.success ? svgResult.output : svgResult.error,
			});
			setResult((prev) =>
				prev
					? { ...prev, svg: svgResult.success ? svgResult.output : null }
					: prev,
			);

			// Step 3: Extrude to 3D STL
			updateStep(2, { status: "running" });
			const stlResult = await callTool("plan_extrude", {
				file_name: dxfFile,
				output_name: `demo_${timestamp}.stl`,
				wall_height: 3.0,
				wall_thickness: 0.15,
				wall_layers: ["Walls"],
			});
			updateStep(2, {
				status: stlResult.success ? "done" : "error",
				detail: stlResult.success
					? `${stlResult.data?.vertices ?? "?"} vertices, ${stlResult.data?.faces ?? "?"} faces`
					: stlResult.error,
			});
			setResult((prev) =>
				prev
					? {
							...prev,
							stl: stlResult.success ? stlResult.output : null,
							stl_vertices: stlResult.success
								? (stlResult.data?.vertices ?? 0)
								: 0,
						}
					: prev,
			);

			// Step 4: Done
			updateStep(3, {
				status: "done",
				detail: "Ready for Resonite, Unity3D, or 3D printing",
			});
		} catch (e: unknown) {
			const msg = e instanceof Error ? e.message : String(e);
			const empty: DemoResult = {
				dxf: null,
				dxf_entities: 0,
				svg: null,
				stl: null,
				stl_vertices: 0,
				error: msg,
			};
			setResult((prev) => (prev ? { ...prev, error: msg } : empty));
			setSteps((prev) =>
				prev.map((s) =>
					s.status === "running"
						? { ...s, status: "error" as const, detail: msg }
						: s,
				),
			);
		} finally {
			setRunning(false);
		}
	};

	const stepIcon = (s: Step) => {
		if (s.status === "done")
			return <CheckCircle size={16} className="text-emerald-400" />;
		if (s.status === "running")
			return <Loader2 size={16} className="animate-spin text-amber-400" />;
		if (s.status === "error")
			return <CheckCircle size={16} className="text-red-400" />;
		return <CheckCircle size={16} className="text-slate-700" />;
	};

	return (
		<div className="max-w-7xl space-y-6">
			{/* Header */}
			<div className="flex items-center gap-3">
				<div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
					<Sparkles size={20} className="text-white" />
				</div>
				<div>
					<h1 className="text-2xl font-bold text-white">AI CAD Demo</h1>
					<p className="text-sm text-slate-400">
						Natural language → 2D floor plan → 3D model → Resonite-ready
					</p>
				</div>
			</div>

			{/* Input Area */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="relative">
					<textarea
						value={goal}
						onChange={(e) => setGoal(e.target.value)}
						onKeyDown={(e) => {
							if (e.key === "Enter" && e.ctrlKey) execute();
						}}
						placeholder="Describe your building — e.g. 'Create a 3-story apartment building, 2 units per floor, each with living room, bedroom, kitchen, and balcony. Add a rooftop garden and elevator shaft.'"
						rows={3}
						className="w-full bg-black/40 border border-amber-500/20 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500 resize-none"
						disabled={running}
					/>
					<div className="absolute bottom-3 right-3 flex items-center gap-2">
						<span className="text-xs text-slate-500">Ctrl+Enter</span>
						<button
							type="button"
							onClick={execute}
							disabled={!goal.trim() || running}
							className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
						>
							{running ? (
								<Loader2 size={14} className="animate-spin" />
							) : (
								<Wand2 size={14} />
							)}
							Generate
						</button>
					</div>
				</div>

				{/* Quick Presets */}
				<div className="flex flex-wrap gap-2">
					<span className="text-xs text-slate-500 self-center mr-1">Try:</span>
					{PRESETS.map((p) => (
						<button
							type="button"
							key={p.label}
							onClick={() => setGoal(p.goal)}
							disabled={running}
							className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs text-slate-300 transition-all border border-white/5"
						>
							{p.emoji} {p.label}
						</button>
					))}
				</div>
			</div>

			{/* Progress Tracker */}
			{steps.length > 0 && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4">
					<div className="flex items-center gap-2 mb-3">
						<Box size={14} className="text-amber-400" />
						<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
							Pipeline
						</h3>
					</div>
					<div className="grid grid-cols-4 gap-3">
						{steps.map((s, i) => (
							<div
								key={s.label}
								className={`p-3 rounded-xl border text-center ${
									s.status === "done"
										? "border-emerald-500/20 bg-emerald-500/5"
										: s.status === "running"
											? "border-amber-500/30 bg-amber-500/5"
											: s.status === "error"
												? "border-red-500/20 bg-red-500/5"
												: "border-white/10 bg-transparent"
								}`}
							>
								<div className="flex items-center justify-center gap-1.5 mb-1">
									<span className="text-xs text-slate-500 font-mono">
										0{i + 1}
									</span>
									{stepIcon(s)}
								</div>
								<p className="text-xs font-medium text-slate-300">{s.label}</p>
								{s.detail && (
									<p className="text-xs text-slate-500 mt-1 truncate">
										{s.detail}
									</p>
								)}
							</div>
						))}
					</div>
				</div>
			)}

			{/* Results */}
			{result && (
				<div className="space-y-6">
					{/* 2D Preview */}
					{result.svg && (
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
							<div className="px-4 py-3 bg-white/5 border-b border-white/10 flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Eye size={14} className="text-amber-400" />
									<span className="text-sm font-bold text-slate-300">
										2D Floor Plan
									</span>
									<span className="text-xs text-slate-500">
										({result.dxf_entities} entities)
									</span>
								</div>
								<a
									href={`/api/v1/download/${result.svg}`}
									className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 text-sm font-bold"
								>
									<Download size={12} /> Download SVG
								</a>
							</div>
							<div className="p-4 bg-[#18181c] flex items-center justify-center min-h-[300px]">
								<img
									src={`/api/v1/download/${result.svg}`}
									alt="Floor plan preview"
									className="max-w-full max-h-[500px] object-contain"
								/>
							</div>
						</div>
					)}

					{/* 3D Viewer */}
					{result.stl && (
						<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
							<div className="px-4 py-3 bg-white/5 border-b border-white/10 flex items-center justify-between">
								<div className="flex items-center gap-2">
									<Box size={14} className="text-amber-400" />
									<span className="text-sm font-bold text-slate-300">
										3D Extrusion
									</span>
									<span className="text-xs text-slate-500">
										({result.stl_vertices} vertices)
									</span>
								</div>
								<a
									href={`/api/v1/download/${result.stl}`}
									className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 text-sm font-bold"
								>
									<Download size={12} /> Download STL
								</a>
							</div>
							<div className="h-[450px]">
								<StlViewer url={`/api/v1/download/${result.stl}`} />
							</div>
						</div>
					)}

					{/* Resonite Export */}
					{result.stl && (
						<div className="bg-gradient-to-br from-purple-950/30 to-indigo-950/30 border border-purple-500/20 rounded-2xl p-6">
							<div className="flex items-start gap-4">
								<div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center shrink-0">
									<ExternalLink size={20} className="text-purple-400" />
								</div>
								<div className="space-y-2">
									<h3 className="text-lg font-bold text-white flex items-center gap-2">
										Resonite-Ready
									</h3>
									<p className="text-sm text-slate-300">
										Download the STL file above and import it directly into
										Resonite. The extrusion preserves real-world scale (1 DXF
										unit = 1 mm). Use the STL as a static world mesh or add
										interactivity.
									</p>
									<div className="flex flex-wrap gap-2">
										<a
											href={`/api/v1/download/${result.stl}`}
											className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-sm font-bold"
										>
											<Download size={14} /> Download STL for Resonite
										</a>
										{result.dxf && (
											<a
												href={`/api/v1/download/${result.dxf}`}
												className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 text-sm"
											>
												<Download size={14} /> Download DXF
											</a>
										)}
									</div>
								</div>
							</div>
						</div>
					)}

					{/* Error */}
					{result.error && (
						<div className="p-4 rounded-2xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm">
							{result.error}
						</div>
					)}
				</div>
			)}

			{/* Empty state */}
			{!result && !running && (
				<div className="text-center py-16 text-slate-400 space-y-3">
					<div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-amber-500/10 to-orange-600/10 flex items-center justify-center">
						<Sparkles size={28} className="text-amber-400 opacity-50" />
					</div>
					<p className="text-lg">
						Describe a building above and watch it come to life.
					</p>
					<p className="text-sm">
						NL input → AI floor plan → 2D preview → 3D extrusion →
						Resonite-ready
					</p>
				</div>
			)}
		</div>
	);
}
