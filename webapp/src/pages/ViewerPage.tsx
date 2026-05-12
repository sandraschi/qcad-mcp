import { useState, useEffect } from "react";
import { Upload, Loader2, Eye, EyeOff, RotateCw } from "lucide-react";

export default function ViewerPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [svgUrl, setSvgUrl] = useState("");
  const [error, setError] = useState("");
  const [layers, setLayers] = useState<string[]>([]);
  const [enabledLayers, setEnabledLayers] = useState<Set<string>>(new Set());
  const [info, setInfo] = useState<any>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError("");

    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch("/api/v1/upload", { method: "POST", body: fd });
      const j = await r.json();
      if (!j.success) throw new Error(j.detail || "Upload failed");

      // Get layer info
      const infoR = await fetch("/api/v1/control/tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "plan_info", arguments: { file_name: file.name } }),
      });
      const infoJ = await infoR.json();
      if (infoJ.success && infoJ.data?.layers) {
        const names = infoJ.data.layers.map((l: any) => l.name);
        setLayers(names);
        setEnabledLayers(new Set(names));
        setInfo(infoJ.data);
      }

      // Generate SVG
      const svgR = await fetch("/api/v1/control/tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool: "plan_to_svg",
          arguments: { file_name: file.name, output_name: `${file.name}.svg`, background: "#0a0a0c" },
        }),
      });
      const svgJ = await svgR.json();
      if (svgJ.success) {
        setSvgUrl(`/api/v1/download/${svgJ.output}?t=${Date.now()}`);
      } else {
        setError(svgJ.error || "SVG generation failed");
      }
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setUploading(false);
    }
  };

  const toggleLayer = (name: string) => {
    const next = new Set(enabledLayers);
    if (next.has(name)) next.delete(name); else next.add(name);
    setEnabledLayers(next);
  };

  const refreshSvg = async () => {
    if (!file) return;
    setError("");
    try {
      const selLayers = layers.filter((l) => enabledLayers.has(l));
      const svgR = await fetch("/api/v1/control/tool", {
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
        setSvgUrl(`/api/v1/download/${svgJ.output}?t=${Date.now()}`);
      } else {
        setError(svgJ.error || "SVG generation failed");
      }
    } catch (e: any) {
      setError(e.message || String(e));
    }
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold text-white">DXF Viewer</h1>
      <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
        <label className="block border-2 border-dashed border-white/10 rounded-xl p-8 text-center cursor-pointer hover:border-amber-500/40 transition-all">
          <Upload className="mx-auto mb-2 text-slate-300" size={32} />
          <p className="text-slate-400">{file ? file.name : "Drop a DXF file here or click to browse"}</p>
          <input type="file" accept=".dxf,.dwg" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        <button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="w-full py-3 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white font-bold flex items-center justify-center gap-2"
        >
          {uploading ? <Loader2 className="animate-spin" size={18} /> : <Eye size={18} />}
          {uploading ? "Processing..." : "Upload DXF & Preview"}
        </button>
        {error && <div className="p-3 rounded-xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm">{error}</div>}
      </div>

      {layers.length > 0 && (
        <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Layers</h3>
            <button onClick={refreshSvg} className="ml-auto flex items-center gap-1 px-3 py-1 rounded-lg bg-white/10 text-sm text-slate-400 hover:text-white">
              <RotateCw size={12} /> Refresh
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {layers.map((l) => (
              <button
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
        <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 overflow-auto" style={{ maxHeight: "70vh" }}>
          <img src={svgUrl} alt="Floor plan preview" className="w-full" />
        </div>
      )}

      {info && (
        <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Plan Info</h3>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div className="text-slate-300">Entities: <span className="text-slate-300">{info.entity_total}</span></div>
            <div className="text-slate-300">Layers: <span className="text-slate-300">{info.layer_count}</span></div>
            <div className="text-slate-300">Blocks: <span className="text-slate-300">{info.block_count}</span></div>
            <div className="text-slate-300">DXF Version: <span className="text-slate-300">{info.dxf_version}</span></div>
            {info.bounding_box && (
              <div className="col-span-2 text-slate-300">
                BBox: <span className="text-slate-300">
                  [{info.bounding_box.xmin?.toFixed(1)}, {info.bounding_box.ymin?.toFixed(1)}] — [{info.bounding_box.xmax?.toFixed(1)}, {info.bounding_box.ymax?.toFixed(1)}]
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
