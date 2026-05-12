import { useState, useEffect } from "react";
import { Play, Loader2, CheckCircle, XCircle, BarChart3, Info, FileText } from "lucide-react";

export default function BatchPage() {
  const [files, setFiles] = useState<{ name: string }[]>([]);
  const [tool, setTool] = useState("plan_info");
  const [results, setResults] = useState<any[] | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/v1/files").then(r => r.json()).then(j => {
      const all = [...(j.uploads || []), ...(j.outputs || [])].filter((f: any) => f.name.match(/\.(dxf|dwg)$/i));
      setFiles(all);
    }).catch(() => {});
  }, []);

  const run = async () => {
    setRunning(true); setError(""); setResults(null);
    try {
      const r = await fetch("/api/v1/batch", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, args: {} }),
      });
      const j = await r.json();
      if (j.results) setResults(j.results);
      else setError(j.error || "Batch run failed");
    } catch (e: any) { setError(e.message); }
    finally { setRunning(false); }
  };

  return (
    <div className="max-w-4xl space-y-6">
      <h1 className="text-2xl font-bold text-white flex items-center gap-3"><Play className="text-amber-400" /> Batch Pipeline</h1>

      <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-4">
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">Tool:</span>
          <select value={tool} onChange={e => setTool(e.target.value)}
            className="bg-black/40 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white outline-none focus:border-amber-500"
          >
            <option value="plan_info">plan_info (metadata)</option>
            <option value="plan_analyse">plan_analyse (room detection)</option>
          </select>
          <span className="text-sm text-slate-500">{files.length} file{files.length !== 1 ? "s" : ""} in depot</span>
          <button onClick={run} disabled={running || files.length === 0}
            className="ml-auto flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white text-sm font-bold"
          >{running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? "Running..." : `Run on ${files.length} files`}
          </button>
        </div>
        {error && <p className="text-red-400 text-sm">{error}</p>}
      </div>

      {results && (
        <div className="space-y-2">
          <p className="text-sm text-slate-400">
            {results.filter(r => r.success).length}/{results.length} succeeded
          </p>
          {results.map((r, i) => (
            <div key={i} className={`bg-[#1e1e26] border rounded-xl p-3 ${r.success ? "border-emerald-500/20" : "border-red-500/20"}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {r.success ? <CheckCircle size={16} className="text-emerald-400" /> : <XCircle size={16} className="text-red-400" />}
                  <span className="text-sm font-bold text-white">{r.file}</span>
                </div>
                <span className="text-xs text-slate-500">{r.success ? "OK" : "Failed"}</span>
              </div>
              {r.success && tool === "plan_info" && (
                <div className="mt-2 text-xs text-slate-400 space-y-0.5">
                  <span>Entities: {r.data?.entity_total || "?"} · </span>
                  <span>Layers: {r.data?.layer_count || "?"} · </span>
                  <span>Blocks: {r.data?.block_count || "?"} · </span>
                  <span>DXF: {r.data?.dxf_version || "?"}</span>
                </div>
              )}
              {r.success && tool === "plan_analyse" && (
                <div className="mt-2 text-xs text-slate-400 space-y-0.5">
                  <span>Rooms: {r.data?.rooms?.length || "0"} · </span>
                  <span>Wall length: {r.data?.wall_length_m ? `${r.data.wall_length_m.toFixed(1)}m` : "?"}</span>
                </div>
              )}
              {r.error && <p className="mt-1 text-xs text-red-400">{r.error}</p>}
            </div>
          ))}
        </div>
      )}

      {!running && !results && (
        <div className="text-center py-12 text-slate-600">
          <Play size={48} className="mx-auto mb-4 opacity-30" />
          <p>Select a tool and run it on all DXF/DWG files in the depot.</p>
        </div>
      )}
    </div>
  );
}
