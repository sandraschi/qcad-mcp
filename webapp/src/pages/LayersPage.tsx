import { ExternalLink, Layers, Lock, RotateCw, Save, Snowflake, Sun, Trash2, Unlock } from "lucide-react";
import { useEffect, useState } from "react";

interface LayerInfo {
	name: string;
	color: number;
	frozen: boolean;
	locked: boolean;
}

export default function LayersPage() {
	const [files, setFiles] = useState<{ name: string }[]>([]);
	const [selected, setSelected] = useState("");
	const [layers, setLayers] = useState<LayerInfo[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");
	const [status, setStatus] = useState("");

	useEffect(() => {
		fetch("/api/v1/files")
			.then((r) => r.json())
			.then((j) => {
				const all = [...(j.uploads || []), ...(j.outputs || [])].filter((f: { name: string }) =>
					f.name.match(/\.(dxf|dwg)$/i),
				);
				setFiles(all);
			})
			.catch(() => {});
	}, []);

	const loadLayers = async (fn: string) => {
		setSelected(fn);
		setLoading(true);
		setError("");
		setLayers([]);
		try {
			const r = await fetch(`/api/v1/layers/${encodeURIComponent(fn)}`);
			const j = await r.json();
			if (j.success) setLayers(j.layers);
			else setError(j.error || "Failed to load layers");
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setLoading(false);
		}
	};

	const applyOp = async (op: string, layerFilter: string, extra: Record<string, unknown> = {}) => {
		setStatus(`${op} on '${layerFilter}'...`);
		try {
			const r = await fetch(`/api/v1/layers/${encodeURIComponent(selected)}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					operations: [{ op, layer_filter: layerFilter, ...extra }],
				}),
			});
			const j = await r.json();
			if (j.success) {
				setStatus(`${op}: OK`);
				loadLayers(selected);
			} else setError(j.error || `${op} failed`);
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		}
	};

	const setColor = async (layer: string, color: number) => {
		await applyOp("layer-set-color", layer, { color });
	};

	return (
		<div className="max-w-4xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Layers className="text-amber-400" /> Layer Manager
			</h1>

			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-3">
				<label htmlFor="layer-file-select" className="text-sm text-slate-400">
					Select a DXF/DWG file
				</label>
				<select
					id="layer-file-select"
					value={selected}
					onChange={(e) => e.target.value && loadLayers(e.target.value)}
					className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-amber-500"
				>
					<option value="">— Choose file —</option>
					{files.map((f) => (
						<option key={f.name} value={f.name}>
							{f.name}
						</option>
					))}
				</select>
				{error && <p className="text-red-400 text-sm">{error}</p>}
			</div>

			{loading && <p className="text-slate-400 text-sm">Loading layers...</p>}

			{layers.length > 0 && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
					<div className="grid grid-cols-[1fr_80px_80px_80px_60px] gap-2 p-3 border-b border-white/10 text-xs text-slate-400 uppercase font-bold tracking-wider bg-black/20">
						<span>Layer</span>
						<span>Color</span>
						<span>Freeze</span>
						<span>Lock</span>
						<span />
					</div>
					{layers.map((l) => (
						<div
							key={l.name}
							className="grid grid-cols-[1fr_80px_80px_80px_60px] gap-2 items-center p-3 border-b border-white/5 hover:bg-white/[0.03] text-sm"
						>
							<span className="text-white truncate font-medium">{l.name}</span>

							<div className="flex items-center gap-1">
								<input
									type="number"
									min={1}
									max={255}
									defaultValue={l.color}
									onBlur={(e) => {
										const v = Number.parseInt(e.target.value);
										if (v !== l.color) setColor(l.name, v);
									}}
									className="w-14 bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-xs text-white text-center outline-none focus:border-amber-500"
								/>
							</div>

							<button
								type="button"
								onClick={() => applyOp(l.frozen ? "layer-thaw" : "layer-freeze", l.name)}
								className={`flex items-center justify-center gap-1 px-2 py-1 rounded-lg text-xs font-bold transition-all ${l.frozen ? "bg-blue-500/20 text-blue-400" : "bg-white/10 text-slate-400 hover:text-white"}`}
							>
								{l.frozen ? <Sun size={12} /> : <Snowflake size={12} />}
							</button>

							<button
								type="button"
								onClick={() => applyOp(l.locked ? "layer-unlock" : "layer-lock", l.name)}
								className={`flex items-center justify-center gap-1 px-2 py-1 rounded-lg text-xs font-bold transition-all ${l.locked ? "bg-red-500/20 text-red-400" : "bg-white/10 text-slate-400 hover:text-white"}`}
							>
								{l.locked ? <Unlock size={12} /> : <Lock size={12} />}
							</button>

							<button
								type="button"
								onClick={() => applyOp("delete", l.name)}
								className="flex items-center justify-center p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
							>
								<Trash2 size={14} />
							</button>
						</div>
					))}
				</div>
			)}

			{layers.length > 0 && (
				<div className="flex flex-wrap gap-2">
					<button
						type="button"
						onClick={() => applyOp("layer-freeze", "")}
						className="flex items-center gap-1 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/[0.12] text-sm text-slate-300 font-bold"
					>
						<Snowflake size={14} /> Freeze All
					</button>
					<button
						type="button"
						onClick={() => applyOp("layer-thaw", "")}
						className="flex items-center gap-1 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/[0.12] text-sm text-slate-300 font-bold"
					>
						<Sun size={14} /> Thaw All
					</button>
					<button
						type="button"
						onClick={() => applyOp("layer-lock", "")}
						className="flex items-center gap-1 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/[0.12] text-sm text-slate-300 font-bold"
					>
						<Lock size={14} /> Lock All
					</button>
					<button
						type="button"
						onClick={() => applyOp("layer-unlock", "")}
						className="flex items-center gap-1 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/[0.12] text-sm text-slate-300 font-bold"
					>
						<Unlock size={14} /> Unlock All
					</button>
				</div>
			)}

			{status && <p className="text-sm text-emerald-400">{status}</p>}
		</div>
	);
}
