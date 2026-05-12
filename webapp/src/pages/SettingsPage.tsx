import { Settings, Cpu, Box } from "lucide-react";
import { useEffect, useState } from "react";

export default function SettingsPage() {
  const [ollamaUrl, setOllamaUrl] = useState("http://192.168.1.11:11434");
  const [model, setModel] = useState("gemma3:1b");
  const [qcadProPath, setQcadProPath] = useState("");
  const [wallHeight, setWallHeight] = useState(3.0);
  const [wallThickness, setWallThickness] = useState(0.3);
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch("/api/v1/settings")
      .then((r) => r.json())
      .then((j) => {
        if (j.ollama_url) setOllamaUrl(j.ollama_url);
        if (j.model) setModel(j.model);
        if (j.qcad_pro_path) setQcadProPath(j.qcad_pro_path);
        if (j.default_wall_height) setWallHeight(j.default_wall_height);
        if (j.default_wall_thickness) setWallThickness(j.default_wall_thickness);
      })
      .catch(() => {});
  }, []);

  const save = async () => {
    setStatus("Saving...");
    try {
      await fetch("/api/v1/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ollama_url: ollamaUrl,
          model,
          qcad_pro_path: qcadProPath,
          default_wall_height: wallHeight,
          default_wall_thickness: wallThickness,
        }),
      });
      setStatus("Saved.");
    } catch {
      setStatus("Error saving.");
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-white flex items-center gap-3">
        <Settings className="text-amber-400" /> Settings
      </h1>

      <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Box size={16} className="text-amber-400" />
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Extrusion Defaults</h3>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <label className="block text-sm text-slate-400">
            Default Wall Height (m)
            <input type="number" step="0.1" min="0.5" value={wallHeight} onChange={(e) => setWallHeight(parseFloat(e.target.value) || 3)} className="mt-1 w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />
          </label>
          <label className="block text-sm text-slate-400">
            Default Wall Thickness (m)
            <input type="number" step="0.05" min="0.05" value={wallThickness} onChange={(e) => setWallThickness(parseFloat(e.target.value) || 0.3)} className="mt-1 w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />
          </label>
        </div>
      </div>

      <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Cpu size={16} className="text-amber-400" />
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">LLM Provider</h3>
        </div>
        <label className="block text-sm text-slate-400">
          Ollama / LMStudio URL
          <input value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="mt-1 w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />
        </label>
        <label className="block text-sm text-slate-400">
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} className="mt-1 w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />
        </label>
      </div>

      <div className="bg-[#0f0f12] border border-white/5 rounded-2xl p-6 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings size={16} className="text-amber-400" />
          <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">QCAD Pro (Optional)</h3>
        </div>
        <label className="block text-sm text-slate-400">
          Path to qcad.exe or qcad (for high-fidelity PDF/DWG)
          <input value={qcadProPath} onChange={(e) => setQcadProPath(e.target.value)} placeholder="C:\Program Files\QCAD\qcad.exe" className="mt-1 w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />
        </label>
        <p className="text-xs text-slate-600">QCAD Pro (Swiss-made, ~€50) enables dwg2pdf and dwg2svg with perfect hatches, text, and dimension rendering.</p>
      </div>

      <button onClick={save} className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-sm font-bold">Save Settings</button>
      {status && <p className="text-sm text-slate-400">{status}</p>}
    </div>
  );
}
