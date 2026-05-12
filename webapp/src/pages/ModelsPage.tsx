import { useEffect, useState } from "react";
import { Box, FileText, Loader2, RefreshCw, Download } from "lucide-react";

export default function ModelsPage() {
  const [uploads, setUploads] = useState<{ name: string; size_kb: number }[]>([]);
  const [outputs, setOutputs] = useState<{ name: string; size_kb: number }[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/v1/files");
      const j = await r.json();
      setUploads(j.uploads || []);
      setOutputs(j.outputs || []);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const fileIcon = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase();
    if (ext === "stl") return <Box size={14} className="text-emerald-400" />;
    if (ext === "svg") return <FileText size={14} className="text-indigo-400" />;
    if (ext === "pdf") return <FileText size={14} className="text-red-400" />;
    return <FileText size={14} className="text-amber-400" />;
  };

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Models & Outputs</h1>
        <button onClick={load} className="flex items-center gap-2 text-sm text-slate-400 hover:text-white">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>
      <div className="grid grid-cols-2 gap-6">
        <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
          <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Uploads</h2>
          {loading ? (
            <Loader2 className="animate-spin" />
          ) : uploads.length === 0 ? (
            <p className="text-slate-400 text-sm">No DXF files uploaded</p>
          ) : (
            uploads.map((f) => (
              <div key={f.name} className="flex items-center justify-between p-3 rounded-xl bg-white/10 text-sm">
                <span className="flex items-center gap-2">
                  <FileText size={14} className="text-amber-400" /> {f.name}
                </span>
                <span className="text-slate-300">{f.size_kb} KB</span>
              </div>
            ))
          )}
        </div>
        <div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
          <h2 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Outputs</h2>
          {outputs.length === 0 ? (
            <p className="text-slate-400 text-sm">No outputs yet — upload a DXF and use the tools</p>
          ) : (
            outputs.map((f) => (
              <div key={f.name} className="flex items-center justify-between p-3 rounded-xl bg-white/10 text-sm">
                <span className="flex items-center gap-2">
                  {fileIcon(f.name)} {f.name}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-slate-300">{f.size_kb} KB</span>
                  <a
                    href={`/api/v1/download/${f.name}`}
                    download
                    className="text-emerald-400 hover:text-emerald-300 text-sm font-bold"
                  >
                    <Download size={14} />
                  </a>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
