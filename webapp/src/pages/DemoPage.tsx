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

type Entity = Record<string, unknown>;

function generateEntities(goal: string): { entities: Entity[]; layers: { name: string; color: number; description: string }[] } {
	const g = goal.toLowerCase();
	const mm = (m: number) => Math.round(m * 1000);

	const layers: { name: string; color: number; description: string }[] = [
		{ name: "Walls", color: 7, description: "Wall lines" },
		{ name: "Columns", color: 8, description: "Structural columns" },
		{ name: "Doors", color: 3, description: "Door openings" },
		{ name: "Text", color: 2, description: "Room labels" },
		{ name: "Dimensions", color: 6, description: "Measurement annotations" },
		{ name: "Detail", color: 5, description: "Detail elements" },
	];

	const entities: Entity[] = [];

	// Baroque church
	if (g.includes("baroque") || g.includes("church") || g.includes("cathedral") || g.includes("basilica")) {
		const W = mm(45), H = mm(20); // nave dimensions
		const apseR = mm(6);
		const transeptW = mm(10), transeptH = mm(28);
		const chapelW = mm(5), chapelH = mm(5);
		// Nave
		entities.push({ type: "rect", x1: 0, y1: 0, x2: W, y2: H, layer: "Walls" });
		// Apse (semi-circle approximated as rect + text)
		entities.push({ type: "line", x1: W, y1: H/2 - apseR, x2: W + apseR, y2: H/2 - apseR, layer: "Walls" });
		entities.push({ type: "line", x1: W + apseR, y1: H/2 - apseR, x2: W + apseR, y2: H/2 + apseR, layer: "Walls" });
		entities.push({ type: "line", x1: W + apseR, y1: H/2 + apseR, x2: W, y2: H/2 + apseR, layer: "Walls" });
		// Transept (cross arms)
		const tx = Math.round(W * 0.4);
		entities.push({ type: "rect", x1: tx, y1: -transeptH/2 + H/2, x2: tx + transeptW, y2: transeptH/2 + H/2, layer: "Walls" });
		// Side chapels
		for (let i = 0; i < 4; i++) {
			const cx = Math.round(W * 0.15 + i * W * 0.2);
			entities.push({ type: "rect", x1: cx, y1: H, x2: cx + chapelW, y2: H + chapelH, layer: "Walls" });
			entities.push({ type: "rect", x1: cx, y1: -chapelH, x2: cx + chapelW, y2: 0, layer: "Walls" });
		}
		// Columns along nave
		for (let i = 0; i < 6; i++) {
			const cx = Math.round(W * 0.12 + i * W * 0.14);
			entities.push({ type: "circle", x: cx, y: Math.round(H * 0.25), r: 200, layer: "Columns" });
			entities.push({ type: "circle", x: cx, y: Math.round(H * 0.75), r: 200, layer: "Columns" });
		}
		// Altar
		entities.push({ type: "rect", x1: W - mm(1), y1: H/2 - mm(1.5), x2: W + mm(1), y2: H/2 + mm(1.5), layer: "Detail" });
		// Labels
		entities.push({ type: "text", x: W/2 - mm(3), y: H/2 - mm(1), h: 800, text: "NAVE", layer: "Text" });
		entities.push({ type: "text", x: W + mm(2), y: H/2 - mm(0.5), h: 400, text: "APSE", layer: "Text" });
		entities.push({ type: "text", x: tx + mm(1), y: -mm(2), h: 400, text: "TRANSEPT", layer: "Text" });
		entities.push({ type: "text", x: W/2 - mm(2), y: H + mm(2), h: 400, text: "SIDE CHAPEL", layer: "Text" });

	// Mob compound
	} else if (g.includes("mob") || g.includes("compound") || g.includes("mafia") || g.includes("estate") || g.includes("villa")) {
		const P = mm(60), Q = mm(50); // perimeter
		// Perimeter wall
		entities.push({ type: "rect", x1: 0, y1: 0, x2: P, y2: Q, layer: "Walls" });
		// Guard towers at corners
		entities.push({ type: "rect", x1: -mm(1), y1: -mm(1), x2: mm(3), y2: mm(3), layer: "Detail" });
		entities.push({ type: "rect", x1: P - mm(2), y1: -mm(1), x2: P + mm(2), y2: mm(3), layer: "Detail" });
		entities.push({ type: "rect", x1: -mm(1), y1: Q - mm(2), x2: mm(3), y2: Q + mm(2), layer: "Detail" });
		entities.push({ type: "rect", x1: P - mm(2), y1: Q - mm(2), x2: P + mm(2), y2: Q + mm(2), layer: "Detail" });
		// Main villa
		const vx = mm(15), vy = mm(10), vw = mm(20), vh = mm(18);
		entities.push({ type: "rect", x1: vx, y1: vy, x2: vx + vw, y2: vy + vh, layer: "Walls" });
		// Pool
		entities.push({ type: "rect", x1: mm(38), y1: mm(8), x2: mm(52), y2: mm(16), layer: "Detail" });
		// Guest house
		entities.push({ type: "rect", x1: mm(5), y1: vy + vh + mm(4), x2: mm(14), y2: vy + vh + mm(10), layer: "Walls" });
		// Gatehouse at entrance
		entities.push({ type: "rect", x1: P/2 - mm(3), y1: 0, x2: P/2 + mm(3), y2: mm(4), layer: "Walls" });
		// Driveway
		entities.push({ type: "line", x1: P/2, y1: mm(4), x2: P/2, y2: vy, layer: "Detail" });
		// Labels
		entities.push({ type: "text", x: vx + mm(4), y: vy + mm(7), h: 700, text: "VILLA", layer: "Text" });
		entities.push({ type: "text", x: mm(40), y: mm(9), h: 400, text: "POOL", layer: "Text" });
		entities.push({ type: "text", x: mm(6), y: vy + vh + mm(5), h: 350, text: "GUEST", layer: "Text" });
		entities.push({ type: "text", x: P/2 - mm(2), y: mm(1), h: 300, text: "GATE", layer: "Text" });

	// Museum / gallery
	} else if (g.includes("museum") || g.includes("gallery") || g.includes("art")) {
		const W = mm(40), H = mm(35);
		entities.push({ type: "rect", x1: 0, y1: 0, x2: W, y2: H, layer: "Walls" });
		// Central atrium
		entities.push({ type: "rect", x1: mm(14), y1: mm(10), x2: mm(26), y2: mm(25), layer: "Walls" });
		// Gallery wings radiating out
		for (let i = 0; i < 4; i++) {
			const angle = (i * 90) * Math.PI / 180;
			const cx = mm(20) + Math.round(Math.cos(angle) * mm(10));
			const cy = mm(17) + Math.round(Math.sin(angle) * mm(10));
			entities.push({ type: "rect", x1: cx - mm(3), y1: cy - mm(2), x2: cx + mm(3), y2: cy + mm(2), layer: "Walls" });
		}
		entities.push({ type: "text", x: mm(15), y: mm(15), h: 600, text: "ATRIUM", layer: "Text" });
		entities.push({ type: "text", x: mm(22), y: mm(2), h: 400, text: "WING A", layer: "Text" });
		entities.push({ type: "text", x: mm(34), y: mm(16), h: 400, text: "WING B", layer: "Text" });

	// Generic: parse dimensions from goal
	} else {
		const dimMatch = g.match(/(\d+)\s*(?:m|meter|metre)/g);
		const nums = dimMatch ? dimMatch.map((s) => parseInt(s.replace(/\D/g, ""))) : [8, 6];
		const w = mm(nums[0] || 8);
		const h = mm(nums[1] || nums[0] || 6);
		const roomCount = Math.min(Math.max(parseInt(g.match(/(\d+)\s*(?:bed|room|bath)/)?.[1] || "4"), 1), 12);

		entities.push({ type: "rect", x1: 0, y1: 0, x2: w, y2: h, layer: "Walls" });
		// Subdivide into rooms
		const cols = Math.ceil(Math.sqrt(roomCount));
		const rows = Math.ceil(roomCount / cols);
		for (let r = 0; r < rows; r++) {
			for (let c = 0; c < cols; c++) {
				if (r * cols + c >= roomCount) break;
				const rx = Math.round(w * c / cols), ry = Math.round(h * r / rows);
				const rw = Math.round(w * (c + 1) / cols) - rx;
				const rh = Math.round(h * (r + 1) / rows) - ry;
				if (r > 0) entities.push({ type: "line", x1: rx, y1: ry, x2: rx + rw, y2: ry, layer: "Walls" });
				if (c > 0) entities.push({ type: "line", x1: rx, y1: ry, x2: rx, y2: ry + rh, layer: "Walls" });
				entities.push({ type: "text", x: rx + Math.round(rw * 0.2), y: ry + Math.round(rh * 0.4), h: Math.min(rw, rh) / 3, text: `ROOM ${r * cols + c + 1}`, layer: "Text" });
			}
		}
		entities.push({ type: "text", x: Math.round(w * 0.3), y: Math.round(h * 0.85), h: 250, text: `${nums[0] || 8}m x ${nums[1] || nums[0] || 6}m`, layer: "Dimensions" });
	}

	return { entities, layers };
}

const PRESETS = [
	{
		label: "Baroque Church",
		emoji: "⛪",
		goal: "Baroque church with 45m nave, semi-circular apse, 28m transept crossing, 6 side chapels, 12 columns along the nave, altar at the east end, and a dome crossing.",
	},
	{
		label: "Mob Compound",
		emoji: "🏰",
		goal: "Mob compound 60m x 50m with perimeter wall, 4 corner guard towers, a 20m x 18m main villa with pool, guest house, gatehouse, and driveway.",
	},
	{
		label: "Art Museum",
		emoji: "🏛️",
		goal: "Modern art museum 40m x 35m with a central atrium, 4 radiating gallery wings, sculpture garden, and cafe.",
	},
	{
		label: "Studio Apartment",
		emoji: "🏠",
		goal: "Open-plan studio apartment 6m x 5m with a kitchenette corner, bathroom 2m x 1.5m, entrance hallway, and a balcony 3m x 1.5m.",
	},
	{
		label: "Office Floor",
		emoji: "🏢",
		goal: "Office floor plan 20m x 15m with 6 private offices 3m x 3m, an open-plan workspace 12m x 8m, two meeting rooms, kitchen, two bathrooms.",
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
				// Fallback: generate rich geometry from goal description
				const { entities, layers } = generateEntities(goal.trim());
				const createResult = await callTool("plan_create", {
					filename: dxfName,
					description: goal.trim(),
					entities,
					layers,
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
				wall_layers: ["Walls", "Columns"],
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
