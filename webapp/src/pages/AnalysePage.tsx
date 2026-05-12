import { useState } from "react";
import { Upload, Loader2, BarChart3, DoorOpen, Ruler } from "lucide-react";

export default function AnalysePage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const handleAnalyse = async () => {
    if (!file) return;
    setLoading(true);
    setError("");

    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch("/api/v1/upload", { method: "POST", body: fd });
      const j = await r.json();
      if (!j.success) throw new Error(j.detail || "Upload failed");

      const conv = await fetch("/api/v1/control/tool", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "plan_analyse", arguments: { file_name: file.name } }),
      });
      const cj = await conv.json();
      if (cj.success) {
        setResult(cj.data);
      } else {
        setError(cj.error || "Analysis failed");
      }
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-white flex items-center gap-3"><BarChart3 className="text-amber-400" /> Plan Analysis</h1>
      <p className="text-sm text-slate-500">Detect rooms from enclosed polylines, calculate areas in m², and identify doors/windows by block names.</p>

      <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-6 space-y-4">
        <label className="block border-2 border-dashed border-white/10 rounded-xl p-6 text-center cursor-pointer hover:border-amber-500/40 transition-all">
          <Upload className="mx-auto mb-2 text-slate-500" size={28} />
          <p className="text-slate-400 text-sm">{file ? file.name : "Drop a DXF floor plan here"}</p>
          <input type="file" accept=".dxf,.dwg" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </label>
        <button
          onClick={handleAnalyse}
          disabled={!file || loading}
          className="w-full py-3 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white font-bold flex items-center justify-center gap-2"
        >
          {loading ? <Loader2 className="animate-spin" size={18} /> : <BarChart3 size={18} />}
          {loading ? "Analysing..." : "Analyse Floor Plan"}
        </button>
        {error && <div className="p-3 rounded-xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm">{error}</div>}
      </div>

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-4 text-center">
              <Ruler size={20} className="mx-auto mb-1 text-amber-400" />
              <p className="text-2xl font-bold text-white">{result.wall_length_m}<span className="text-sm font-normal text-slate-500"> m</span></p>
              <p className="text-xs text-slate-500">Total Wall Length</p>
            </div>
            <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-4 text-center">
              <BarChart3 size={20} className="mx-auto mb-1 text-amber-400" />
              <p className="text-2xl font-bold text-white">{result.rooms?.length || 0}</p>
              <p className="text-xs text-slate-500">Rooms / Spaces</p>
            </div>
            <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-4 text-center">
              <DoorOpen size={20} className="mx-auto mb-1 text-amber-400" />
              <p className="text-2xl font-bold text-white">{result.doors_windows?.length || 0}</p>
              <p className="text-xs text-slate-500">Doors / Windows</p>
            </div>
          </div>

          {result.rooms && result.rooms.length > 0 && (
            <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-4 space-y-2">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Detected Rooms</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-white/5">
                      <th className="py-2 pr-4">#</th>
                      <th className="py-2 pr-4">Layer</th>
                      <th className="py-2 pr-4">Type</th>
                      <th className="py-2 pr-4 text-right">Area (m²)</th>
                      <th className="py-2 pr-4 text-right">Perimeter (m)</th>
                      <th className="py-2 text-right">Vertices</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.rooms.map((room: any, i: number) => (
                      <tr key={i} className="border-b border-white/[0.02] text-slate-300">
                        <td className="py-2 pr-4 text-slate-500">{i + 1}</td>
                        <td className="py-2 pr-4">{room.layer}</td>
                        <td className="py-2 pr-4">
                          <span className={`px-2 py-0.5 rounded text-xs ${room.likely_type === "wall_outline" ? "bg-red-950/30 text-red-400" : "bg-emerald-950/30 text-emerald-400"}`}>
                            {room.likely_type}
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-right font-mono">{room.area_m2}</td>
                        <td className="py-2 pr-4 text-right font-mono">{room.perimeter_m}</td>
                        <td className="py-2 text-right font-mono">{room.vertex_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.doors_windows && result.doors_windows.length > 0 && (
            <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-4 space-y-2">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Doors & Windows</h3>
              <div className="flex flex-wrap gap-2">
                {result.doors_windows.map((item: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 text-sm">
                    <DoorOpen size={12} className="text-amber-400" />
                    <span className="text-slate-300">{item.block}</span>
                    <span className="text-slate-600">on {item.layer}</span>
                    <span className="text-slate-500 text-xs">({item.position.x.toFixed(0)}, {item.position.y.toFixed(0)})</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
