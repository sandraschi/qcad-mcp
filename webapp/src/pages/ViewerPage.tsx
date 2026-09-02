import {
	Download,
	Eye,
	EyeOff,
	Loader2,
	Maximize2,
	Move,
	RotateCw,
	Ruler,
	Upload,
	ZoomIn,
	ZoomOut,
} from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface PlanViewerInfo {
	entity_total: number;
	layer_count: number;
	block_count: number;
	dxf_version: string;
	layers: Array<{ name: string }>;
	bounding_box?: { xmin: number; ymin: number; xmax: number; ymax: number };
}

export default function ViewerPage() {
	const [file, setFile] = useState<File | null>(null);
	const [uploading, setUploading] = useState(false);
	const [svgUrl, setSvgUrl] = useState("");
	const [error, setError] = useState("");
	const [layers, setLayers] = useState<string[]>([]);
	const [enabledLayers, setEnabledLayers] = useState<Set<string>>(new Set());
	const [info, setInfo] = useState<PlanViewerInfo | null>(null);
	const [zoom, setZoom] = useState<number>(100);
	const [autoDimmed, setAutoDimmed] = useState<boolean>(false);
	const [dimming, setDimming] = useState<boolean>(false);

	const handleUpload = async () => {
		if (!file) return;
		setUploading(true);
		setError("");
		setAutoDimmed(false);

		try {
			const fd = new FormData();
			fd.append("file", file);
			const r = await fetch(API_BASE + "/api/v1/upload", { method: "POST", body: fd });
			const j = await r.json();
			if (!j.success) throw new Error(j.detail || "Upload failed");

			// Get layer info
			const infoR = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					tool: "plan_info",
					arguments: { file_name: file.name },
				}),
			});
			const infoJ = await infoR.json();
			if (infoJ.success && infoJ.data?.layers) {
				const names = infoJ.data.layers.map((l: { name: string }) => l.name);
				setLayers(names);
				setEnabledLayers(new Set(names));
				setInfo(infoJ.data);
			}

			// Generate SVG
			const svgR = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					tool: "plan_to_svg",
					arguments: {
						file_name: file.name,
						output_name: `${file.name}.svg`,
						background: "#0a0a0c",
					},
				}),
			});
			const svgJ = await svgR.json();
			if (svgJ.success) {
				setSvgUrl(`${API_BASE}/api/v1/case-files/${svgJ.output}?t=${Date.now()}`);
			} else {
				setError(svgJ.error || "SVG generation failed");
			}
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setUploading(false);
		}
	};

	const handleAutoDimension = async () => {
		if (!file) return;
		setDimming(true);
		setError("");
		try {
			const res = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					tool: "plan_auto_dimension",
					arguments: { file_name: file.name, offset: 400.0 },
				}),
			});
			const j = await res.json();
			if (j.success) {
				setAutoDimmed(true);
				// Re-render SVG with dimensions
				const outName = j.data?.output_name || file.name;
				const svgR = await fetch(API_BASE + "/api/v1/control/tool", {
					method: "POST",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify({
						tool: "plan_to_svg",
						arguments: { file_name: outName, output_name: `${outName}.svg`, background: "#0a0a0c" },
					}),
				});
				const svgJ = await svgR.json();
				if (svgJ.success) {
					setSvgUrl(`${API_BASE}/api/v1/case-files/${svgJ.output}?t=${Date.now()}`);
				}
			} else {
				setError(j.error || "Auto-dimensioning failed");
			}
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setDimming(false);
		}
	};

	const toggleLayer = (name: string) => {
		const next = new Set(enabledLayers);
		if (next.has(name)) next.delete(name);
		else next.add(name);
		setEnabledLayers(next);
	};

	const refreshSvg = async () => {
		if (!file) return;
		setError("");
		try {
			const selLayers = layers.filter((l) => enabledLayers.has(l));
			const svgR = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					tool: "plan_to_svg",
					arguments: {
						file_name: file.name,
						output_name: `${file.name}.svg`,
						layers: selLayers.length === layers.length ? undefined : selLayers,
						background: "#0a0a0c",
					},
				}),
			});
			const svgJ = await svgR.json();
			if (svgJ.success) {
				setSvgUrl(`${API_BASE}/api/v1/case-files/${svgJ.output}?t=${Date.now()}`);
			} else {
				setError(svgJ.error || "SVG generation failed");
			}
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		}
	};

	return (
		<div className="space-y-6 max-w-6xl">
			<div className="flex items-center justify-between">
				<h1 className="text-2xl font-bold text-white">DXF Floor Plan Viewer</h1>
				{file && (
					<button
						type="button"
						onClick={handleAutoDimension}
						disabled={dimming}
						className="flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm font-bold transition-all"
					>
						{dimming ? <Loader2 className="animate-spin" size={16} /> : <Ruler size={16} />}
						{autoDimmed ? "Re-Dimension Plan" : "Auto-Dimension Boundaries"}
					</button>
				)}
			</div>

			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<label className="block border-2 border-dashed border-white/10 rounded-xl p-8 text-center cursor-pointer hover:border-amber-500/40 transition-all">
					<Upload className="mx-auto mb-2 text-slate-300" size={32} />
					<p className="text-slate-400">{file ? file.name : "Drop a DXF file here or click to browse"}</p>
					<input
						type="file"
						accept=".dxf,.dwg"
						className="hidden"
						onChange={(e) => setFile(e.target.files?.[0] || null)}
					/>
				</label>
				<button
					type="button"
					onClick={handleUpload}
					disabled={!file || uploading}
					className="w-full py-3 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white font-bold flex items-center justify-center gap-2"
				>
					{uploading ? <Loader2 className="animate-spin" size={18} /> : <Eye size={18} />}
					{uploading ? "Processing..." : "Upload DXF & Render Preview"}
				</button>
				{error && (
					<div className="p-3 rounded-xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm">{error}</div>
				)}
			</div>

			{layers.length > 0 && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4">
					<div className="flex items-center gap-2 mb-3">
						<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Layers</h3>
						<button
							type="button"
							onClick={refreshSvg}
							className="ml-auto flex items-center gap-1 px-3 py-1 rounded-lg bg-white/10 text-sm text-slate-400 hover:text-white"
						>
							<RotateCw size={12} /> Refresh Layer Overlay
						</button>
					</div>
					<div className="flex flex-wrap gap-2">
						{layers.map((l) => (
							<button
								type="button"
								key={l}
								onClick={() => toggleLayer(l)}
								className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
									enabledLayers.has(l) ? "bg-amber-600 text-white" : "bg-white/10 text-slate-300"
								}`}
							>
								{enabledLayers.has(l) ? <Eye size={12} /> : <EyeOff size={12} />}
								{l}
							</button>
						))}
					</div>
				</div>
			)}

			{svgUrl && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-3">
					<div className="flex items-center justify-between border-b border-white/10 pb-3">
						<div className="flex items-center gap-2">
							<button
								type="button"
								onClick={() => setZoom((z) => Math.max(50, z - 25))}
								className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-slate-300"
								title="Zoom Out"
							>
								<ZoomOut size={16} />
							</button>
							<span className="text-sm font-mono text-slate-300 w-16 text-center">{zoom}%</span>
							<button
								type="button"
								onClick={() => setZoom((z) => Math.min(300, z + 25))}
								className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-slate-300"
								title="Zoom In"
							>
								<ZoomIn size={16} />
							</button>
							<button
								type="button"
								onClick={() => setZoom(100)}
								className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-slate-300"
								title="Reset Zoom"
							>
								<Maximize2 size={16} />
							</button>
						</div>
						<div className="flex items-center gap-2">
							<a
								href={svgUrl}
								download={`${file?.name || "plan"}.svg`}
								className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-bold text-slate-200"
							>
								<Download size={12} /> SVG
							</a>
							{file && (
								<a
									href={`${API_BASE}/api/v1/depot/${file.name}`}
									download
									className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-bold text-slate-200"
								>
									<Download size={12} /> DXF
								</a>
							)}
						</div>
					</div>
					<div
						className="overflow-auto flex items-center justify-center p-4 min-h-[400px] bg-[#0a0a0c] rounded-xl border border-white/5"
						style={{ maxHeight: "70vh" }}
					>
						<div
							style={{
								transform: `scale(${zoom / 100})`,
								transformOrigin: "center center",
								transition: "transform 0.15s ease",
							}}
						>
							<img src={svgUrl} alt="Floor plan preview" className="max-w-full h-auto select-none" />
						</div>
					</div>
				</div>
			)}

			{info && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
					<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Plan Metadata</h3>
					<div className="grid grid-cols-3 gap-2 text-sm">
						<div className="text-slate-300">
							Entities: <span className="text-slate-100 font-semibold">{info.entity_total}</span>
						</div>
						<div className="text-slate-300">
							Layers: <span className="text-slate-100 font-semibold">{info.layer_count}</span>
						</div>
						<div className="text-slate-300">
							Blocks: <span className="text-slate-100 font-semibold">{info.block_count}</span>
						</div>
						<div className="text-slate-300">
							DXF Version: <span className="text-slate-100 font-semibold">{info.dxf_version}</span>
						</div>
						{info.bounding_box && (
							<div className="col-span-2 text-slate-300">
								BBox:{" "}
								<span className="text-slate-100 font-mono">
									[{info.bounding_box.xmin?.toFixed(1)}, {info.bounding_box.ymin?.toFixed(1)}] — [
									{info.bounding_box.xmax?.toFixed(1)}, {info.bounding_box.ymax?.toFixed(1)}]
								</span>
							</div>
						)}
					</div>
				</div>
			)}
		</div>
	);
}
