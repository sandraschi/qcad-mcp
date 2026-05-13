import { Box, Download, Loader2, Settings2, Upload } from "lucide-react";
import { useState } from "react";

interface ExtrudeData {
	size_kb: number;
	wall_count: number;
	vertices: number;
	faces: number;
}

interface ExtrudeResult {
	success: boolean;
	output: string;
	data: ExtrudeData;
}

export default function ExtrudePage() {
	const [file, setFile] = useState<File | null>(null);
	const [uploading, setUploading] = useState(false);
	const [extruding, setExtruding] = useState(false);
	const [result, setResult] = useState<ExtrudeResult | null>(null);
	const [error, setError] = useState("");
	const [wallHeight, setWallHeight] = useState(3.0);
	const [wallThickness, setWallThickness] = useState(0.3);
	const [wallLayers, setWallLayers] = useState("");

	const handleExtrude = async () => {
		if (!file) return;
		setUploading(true);
		setError("");

		try {
			const fd = new FormData();
			fd.append("file", file);
			const r = await fetch("/api/v1/upload", { method: "POST", body: fd });
			const j = await r.json();
			if (!j.success) throw new Error(j.detail || "Upload failed");

			setUploading(false);
			setExtruding(true);

			const stlName = `${file.name.replace(/\.(dxf|dwg)$/i, "")}.stl`;
			const wl = wallLayers.trim() ? wallLayers.split(",").map((s) => s.trim()) : undefined;

			const conv = await fetch("/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					tool: "plan_extrude",
					arguments: {
						file_name: file.name,
						output_name: stlName,
						wall_height: wallHeight,
						wall_thickness: wallThickness,
						wall_layers: wl,
					},
				}),
			});
			const cj = await conv.json();
			if (cj.success) {
				setResult(cj);
			} else {
				setError(cj.error || "Extrusion failed");
			}
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setUploading(false);
			setExtruding(false);
		}
	};

	return (
		<div className="max-w-3xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Box className="text-amber-400" /> Wall Extrusion
			</h1>
			<p className="text-sm text-slate-300">
				Upload a DXF floor plan, configure wall parameters, and generate a 3D STL mesh.
			</p>

			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Settings2 size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Parameters</h3>
				</div>

				<div className="grid grid-cols-2 gap-4">
					<label className="block space-y-1">
						<span className="text-sm text-slate-300">Wall Height (m)</span>
						<input
							type="number"
							step="0.1"
							min="0.5"
							max="20"
							value={wallHeight}
							onChange={(e) => setWallHeight(Number.parseFloat(e.target.value) || 3)}
							className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30"
						/>
					</label>
					<label className="block space-y-1">
						<span className="text-sm text-slate-300">Wall Thickness (m)</span>
						<input
							type="number"
							step="0.05"
							min="0.05"
							max="2"
							value={wallThickness}
							onChange={(e) => setWallThickness(Number.parseFloat(e.target.value) || 0.3)}
							className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30"
						/>
					</label>
				</div>

				<label className="block space-y-1">
					<span className="text-sm text-slate-300">Wall Layers (comma-separated, auto-detect if empty)</span>
					<input
						type="text"
						value={wallLayers}
						onChange={(e) => setWallLayers(e.target.value)}
						placeholder="e.g. walls, WALL-LINE, mauer"
						className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30"
					/>
				</label>
			</div>

			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<label className="block border-2 border-dashed border-white/10 rounded-xl p-6 text-center cursor-pointer hover:border-amber-500/40 transition-all">
					<Upload className="mx-auto mb-2 text-slate-300" size={28} />
					<p className="text-slate-400 text-sm">{file ? file.name : "Drop a DXF floor plan here"}</p>
					<input
						type="file"
						accept=".dxf,.dwg"
						className="hidden"
						onChange={(e) => setFile(e.target.files?.[0] || null)}
					/>
				</label>
				<button
					type="button"
					onClick={handleExtrude}
					disabled={!file || uploading || extruding}
					className="w-full py-3 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white font-bold flex items-center justify-center gap-2"
				>
					{uploading || extruding ? <Loader2 className="animate-spin" size={18} /> : <Box size={18} />}
					{uploading ? "Uploading..." : extruding ? "Extruding walls..." : "Extrude to STL"}
				</button>
				{error && (
					<div className="p-3 rounded-xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm">{error}</div>
				)}
			</div>

			{result && (
				<div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/20 space-y-2">
					<p className="text-emerald-400 font-bold flex items-center gap-2">
						<Download size={16} /> Extrusion Complete
					</p>
					<p className="text-sm text-slate-400">
						{result.output} — {result.data?.size_kb} KB
					</p>
					<p className="text-sm text-slate-400">
						{result.data?.wall_count} wall segments — {result.data?.vertices}+ vertices, {result.data?.faces} faces
					</p>
					<a
						href={`/api/v1/download/${result.output}`}
						download
						className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold"
					>
						<Download size={14} /> Download STL from Depot
					</a>
				</div>
			)}
		</div>
	);
}
