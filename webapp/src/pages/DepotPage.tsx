import { useEffect, useState, useCallback } from "react";
import {
  FileText, Upload, Download, Trash2, Pencil, Plus, X, Search,
  Grid3X3, List, Loader2, Ruler, Layers, Eye, EyeOff,
  ExternalLink, RefreshCw, AlertTriangle, Square, Circle,
  Type, Minus, CornerDownRight, Save
} from "lucide-react";

type DxfFile = {
  name: string;
  size_kb: number;
  size_bytes: number;
  modified: string;
  meta: {
    created?: string;
    description?: string;
    tags?: string[];
    entity_count?: number;
  };
};

type EntityType = "line" | "rect" | "circle" | "text" | "polyline";

type EntitySpec = {
  type: EntityType;
  // line
  x1?: number; y1?: number; x2?: number; y2?: number;
  // rect
  x?: number; y?: number; w?: number; h?: number;
  // circle
  cx?: number; cy?: number; r?: number;
  // text
  content?: string; height?: number;
  // polyline
  points?: number[][]; closed?: boolean;
  // all
  layer?: string;
};

const ENTITY_COLORS: Record<EntityType, string> = {
  line: "text-blue-400", rect: "text-emerald-400", circle: "text-amber-400",
  text: "text-indigo-400", polyline: "text-rose-400",
};

const ENTITY_ICONS: Record<EntityType, any> = {
  line: Minus, rect: Square, circle: Circle, text: Type, polyline: CornerDownRight,
};

const DEFAULT_ENTITIES: Record<EntityType, EntitySpec> = {
  line: { type: "line", x1: 0, y1: 0, x2: 100, y2: 0, layer: "0" },
  rect: { type: "rect", x: 0, y: 0, w: 100, h: 80, layer: "0" },
  circle: { type: "circle", cx: 50, cy: 50, r: 30, layer: "0" },
  text: { type: "text", x: 10, y: 10, content: "Label", height: 5, layer: "0" },
  polyline: { type: "polyline", points: [[0, 0], [100, 0], [100, 50]], closed: false, layer: "0" },
};

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function timeAgo(iso: string) {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  } catch { return ""; }
}

export default function DepotPage() {
  const [files, setFiles] = useState<DxfFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [fileInfo, setFileInfo] = useState<any>(null);

  // Dialogs
  const [showCreate, setShowCreate] = useState(false);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  // Create form
  const [createName, setCreateName] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createLayers, setCreateLayers] = useState<string>("0");
  const [createEntities, setCreateEntities] = useState<EntitySpec[]>([
    { type: "rect", x: 0, y: 0, w: 10000, h: 8000, layer: "walls" },
  ]);
  const [creating, setCreating] = useState(false);

  // Upload
  const [uploading, setUploading] = useState(false);

  // SVG preview for non-selected files (generate on hover/click)
  const [generatingPreview, setGeneratingPreview] = useState<string | null>(null);

  const loadFiles = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch("/api/v1/depot");
      const j = await r.json();
      setFiles(j.files || []);
    } catch { setError("Failed to load depot"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadFiles(); }, [loadFiles]);

  const filtered = files.filter(f =>
    f.name.toLowerCase().includes(search.toLowerCase()) ||
    (f.meta.description || "").toLowerCase().includes(search.toLowerCase())
  );

  const selectFile = async (name: string) => {
    setSelectedFile(name);
    setPreviewUrl("");
    setFileInfo(null);

    // Generate preview SVG
    setGeneratingPreview(name);
    try {
      const svgR = await fetch("/api/v1/control/tool", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tool: "plan_to_svg",
          arguments: { file_name: name, output_name: `_preview_${name}.svg`, background: "#0a0a0c" },
        }),
      });
      const svgJ = await svgR.json();
      if (svgJ.success) setPreviewUrl(`/api/v1/download/${svgJ.output}?t=${Date.now()}`);
    } catch {}
    setGeneratingPreview(null);

    // Get info
    try {
      const infoR = await fetch("/api/v1/control/tool", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "plan_info", arguments: { file_name: name } }),
      });
      const infoJ = await infoR.json();
      if (infoJ.success) setFileInfo(infoJ.data);
    } catch {}
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true); setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch("/api/v1/upload", { method: "POST", body: fd });
      const j = await r.json();
      if (!j.success) throw new Error(j.detail || "Upload failed");
      await loadFiles();
    } catch (err: any) { setError(err.message || "Upload failed"); }
    finally { setUploading(false); e.target.value = ""; }
  };

  const handleCreate = async () => {
    if (!createName) { setError("Filename required"); return; }
    setCreating(true); setError("");
    try {
      const uniqueLayers = [...new Set(createEntities.map(e => e.layer || "0"))];
      const layers = uniqueLayers.map((name, i) => ({ name, color: [7, 5, 3, 2, 6, 1][i % 6] }));

      const r = await fetch("/api/v1/depot/create", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          filename: createName.endsWith(".dxf") ? createName : `${createName}.dxf`,
          entities: createEntities,
          layers,
          description: createDesc,
        }),
      });
      const j = await r.json();
      if (!j.success) throw new Error(j.error || "Creation failed");

      setShowCreate(false);
      setCreateName(""); setCreateDesc(""); setCreateEntities([{ type: "rect", x: 0, y: 0, w: 10000, h: 8000, layer: "walls" }]);
      await loadFiles();
    } catch (err: any) { setError(err.message); }
    finally { setCreating(false); }
  };

  const handleRename = async () => {
    if (!renameTarget || !renameValue) return;
    try {
      const r = await fetch(`/api/v1/depot/${encodeURIComponent(renameTarget)}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: renameValue.endsWith(".dxf") ? renameValue : `${renameValue}.dxf` }),
      });
      if (!r.ok) { const j = await r.json(); throw new Error(j.detail || "Rename failed"); }
      setRenameTarget(null);
      if (selectedFile === renameTarget) setSelectedFile(null);
      await loadFiles();
    } catch (err: any) { setError(err.message); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      const r = await fetch(`/api/v1/depot/${encodeURIComponent(deleteTarget)}`, { method: "DELETE" });
      if (!r.ok) { const j = await r.json(); throw new Error(j.detail || "Delete failed"); }
      setDeleteTarget(null);
      if (selectedFile === deleteTarget) setSelectedFile(null);
      await loadFiles();
    } catch (err: any) { setError(err.message); }
  };

  const handleExport = async (format: string) => {
    if (!selectedFile) return;
    try {
      const outName = `${selectedFile.replace(/\.(dxf|dwg)$/i, "")}.${format}`;
      const r = await fetch("/api/v1/control/tool", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool: "plan_export", arguments: { file_name: selectedFile, format, output_name: outName } }),
      });
      const j = await r.json();
      if (j.success) window.open(`/api/v1/download/${j.output}`, "_blank");
      else setError(j.error || "Export failed");
    } catch (err: any) { setError(err.message); }
  };

  const addEntity = (type: EntityType) => {
    setCreateEntities([...createEntities, { ...DEFAULT_ENTITIES[type] }]);
  };

  const updateEntity = (idx: number, patch: Partial<EntitySpec>) => {
    setCreateEntities(createEntities.map((e, i) => i === idx ? { ...e, ...patch } : e));
  };

  const removeEntity = (idx: number) => {
    setCreateEntities(createEntities.filter((_, i) => i !== idx));
  };

  const fileTypeIcon = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase();
    if (ext === "dxf") return <FileText size={16} className="text-amber-400" />;
    return <FileText size={16} className="text-slate-400" />;
  };

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <FileText className="text-amber-400" /> CAD Depot
        </h1>
        <div className="flex items-center gap-2">
          <button onClick={loadFiles} className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-white/10 text-xs text-slate-400 hover:text-white hover:bg-white/5">
            <RefreshCw size={14} /> Refresh
          </button>
          <label className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold cursor-pointer">
            <Upload size={14} /> {uploading ? "Uploading..." : "Upload DXF"}
            <input type="file" accept=".dxf,.dwg" className="hidden" onChange={handleUpload} disabled={uploading} />
          </label>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold">
            <Plus size={14} /> New DXF
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-950/40 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
          <button onClick={() => setError("")} className="ml-auto text-red-400 hover:text-red-300"><X size={14} /></button>
        </div>
      )}

      {/* Search + view toggle */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-white/10 bg-[#0f0f12] flex-1 max-w-md">
          <Search size={14} className="text-slate-500 shrink-0" />
          <input type="text" placeholder="Search files..." value={search} onChange={e => setSearch(e.target.value)} className="bg-transparent text-sm text-slate-200 placeholder-slate-600 outline-none w-full" />
        </div>
        <div className="flex gap-1 p-1 bg-white/5 rounded-xl">
          <button onClick={() => setViewMode("grid")} className={`p-1.5 rounded-lg ${viewMode === "grid" ? "bg-amber-600 text-white" : "text-slate-500 hover:text-slate-300"}`}><Grid3X3 size={14} /></button>
          <button onClick={() => setViewMode("list")} className={`p-1.5 rounded-lg ${viewMode === "list" ? "bg-amber-600 text-white" : "text-slate-500 hover:text-slate-300"}`}><List size={14} /></button>
        </div>
        <span className="text-xs text-slate-600">{files.length} file{files.length !== 1 ? "s" : ""}</span>
      </div>

      {/* File grid/list */}
      {loading ? (
        <div className="flex items-center justify-center py-20"><Loader2 className="animate-spin text-amber-400" size={32} /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20 text-slate-600 space-y-3">
          <FileText size={48} className="mx-auto opacity-30" />
          <p className="text-lg">{files.length === 0 ? "Depot is empty" : "No files match your search"}</p>
          <p className="text-sm">
            {files.length === 0
              ? "Upload a DXF file or create a new one to get started."
              : "Try a different search term."}
          </p>
          {files.length === 0 && (
            <div className="flex gap-3 justify-center mt-4">
              <label className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold cursor-pointer">
                <Upload size={14} /> Upload DXF
                <input type="file" accept=".dxf,.dwg" className="hidden" onChange={handleUpload} />
              </label>
              <button onClick={() => setShowCreate(true)} className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold">
                <Plus size={14} /> Create New
              </button>
            </div>
          )}
        </div>
      ) : viewMode === "grid" ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filtered.map(f => (
            <div
              key={f.name}
              onClick={() => selectFile(f.name)}
              className={`bg-[#0f0f12] border rounded-2xl p-4 cursor-pointer transition-all hover:border-amber-500/30 space-y-2 ${
                selectedFile === f.name ? "border-amber-500/50 bg-amber-500/5" : "border-white/5"
              }`}
            >
              <div className="flex items-start justify-between">
                {fileTypeIcon(f.name)}
                <div className="flex gap-1">
                  <button onClick={e => { e.stopPropagation(); setRenameTarget(f.name); setRenameValue(f.name.replace(/\.dxf$/i, "")); }} className="text-slate-600 hover:text-slate-300 p-0.5"><Pencil size={12} /></button>
                  <button onClick={e => { e.stopPropagation(); setDeleteTarget(f.name); }} className="text-slate-600 hover:text-red-400 p-0.5"><Trash2 size={12} /></button>
                </div>
              </div>
              <p className="text-sm font-medium text-slate-200 truncate">{f.name}</p>
              <div className="flex items-center justify-between text-xs text-slate-600">
                <span>{f.size_kb} KB</span>
                <span>{timeAgo(f.modified)}</span>
              </div>
              {f.meta.entity_count !== undefined && (
                <div className="flex items-center gap-1 text-xs text-slate-500">
                  <Layers size={10} /> {f.meta.entity_count} entities
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-[#0f0f12] border border-white/5 rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-white/5">
                <th className="py-3 px-4 font-medium">Name</th>
                <th className="py-3 px-4 font-medium">Size</th>
                <th className="py-3 px-4 font-medium">Modified</th>
                <th className="py-3 px-4 font-medium">Entities</th>
                <th className="py-3 px-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(f => (
                <tr
                  key={f.name}
                  onClick={() => selectFile(f.name)}
                  className={`border-b border-white/[0.02] cursor-pointer hover:bg-white/[0.02] ${
                    selectedFile === f.name ? "bg-amber-500/5" : ""
                  }`}
                >
                  <td className="py-3 px-4">
                    <span className="flex items-center gap-2 text-slate-300">
                      {fileTypeIcon(f.name)} {f.name}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-slate-500">{f.size_kb} KB</td>
                  <td className="py-3 px-4 text-slate-500">{formatDate(f.modified)}</td>
                  <td className="py-3 px-4 text-slate-500">{f.meta.entity_count ?? "—"}</td>
                  <td className="py-3 px-4">
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <button onClick={() => { setRenameTarget(f.name); setRenameValue(f.name.replace(/\.dxf$/i, "")); }} className="p-1 text-slate-600 hover:text-slate-300 rounded"><Pencil size={13} /></button>
                      <button onClick={() => setDeleteTarget(f.name)} className="p-1 text-slate-600 hover:text-red-400 rounded"><Trash2 size={13} /></button>
                      <a href={`/api/v1/depot/${encodeURIComponent(f.name)}`} download className="p-1 text-slate-600 hover:text-emerald-400 rounded"><Download size={13} /></a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail panel */}
      {selectedFile && (
        <div className="bg-[#0f0f12] border border-white/5 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
            <h3 className="text-sm font-bold text-slate-300 flex items-center gap-2">
              <FileText size={16} className="text-amber-400" /> {selectedFile}
            </h3>
            <div className="flex items-center gap-2">
              <button onClick={() => handleExport("svg")} className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white">Export SVG</button>
              <button onClick={() => handleExport("pdf")} className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white">Export PDF</button>
              <a href={`/api/v1/depot/${encodeURIComponent(selectedFile)}`} download className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold">
                <Download size={12} /> Download DXF
              </a>
              <button onClick={() => setSelectedFile(null)} className="text-slate-600 hover:text-slate-300 p-1"><X size={14} /></button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 p-4">
            {/* Preview */}
            <div className="lg:col-span-2 bg-[#0a0a0c] border border-white/5 rounded-xl overflow-auto" style={{ maxHeight: "50vh" }}>
              {generatingPreview === selectedFile ? (
                <div className="flex items-center justify-center h-64"><Loader2 className="animate-spin text-slate-500" size={24} /></div>
              ) : previewUrl ? (
                <img src={previewUrl} alt="Preview" className="w-full" />
              ) : (
                <div className="flex items-center justify-center h-64 text-slate-600 text-sm">Preview not available</div>
              )}
            </div>

            {/* Metadata */}
            <div className="space-y-3">
              <div className="bg-[#0a0a0c] border border-white/5 rounded-xl p-3 space-y-2">
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Info</h4>
                {(() => {
                  const f = files.find(x => x.name === selectedFile);
                  if (!f) return null;
                  return (
                    <>
                      <div className="flex justify-between text-xs"><span className="text-slate-500">Size</span><span className="text-slate-300">{f.size_kb} KB</span></div>
                      <div className="flex justify-between text-xs"><span className="text-slate-500">Created</span><span className="text-slate-300">{f.meta.created ? formatDate(f.meta.created) : "—"}</span></div>
                      <div className="flex justify-between text-xs"><span className="text-slate-500">Modified</span><span className="text-slate-300">{formatDate(f.modified)}</span></div>
                      {f.meta.description && (
                        <div className="text-xs text-slate-400 pt-1 border-t border-white/5">{f.meta.description}</div>
                      )}
                    </>
                  );
                })()}
              </div>

              {fileInfo && (
                <div className="bg-[#0a0a0c] border border-white/5 rounded-xl p-3 space-y-2">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Entities</h4>
                  {Object.entries(fileInfo.entity_counts || {}).map(([type, count]) => (
                    <div key={type} className="flex justify-between text-xs">
                      <span className="text-slate-500">{type}</span>
                      <span className="text-slate-300">{String(count)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between text-xs font-bold pt-1 border-t border-white/5">
                    <span className="text-slate-500">Total</span>
                    <span className="text-slate-200">{fileInfo.entity_total}</span>
                  </div>
                </div>
              )}

              {fileInfo?.layers && (
                <div className="bg-[#0a0a0c] border border-white/5 rounded-xl p-3 space-y-2">
                  <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">Layers</h4>
                  {fileInfo.layers.map((l: any) => (
                    <div key={l.name} className="flex items-center gap-2 text-xs">
                      <span className="w-3 h-3 rounded-full" style={{ backgroundColor: l.color === 7 ? "#ccc" : l.color === 1 ? "#f00" : l.color === 2 ? "#ff0" : l.color === 3 ? "#0f0" : l.color === 4 ? "#0ff" : l.color === 5 ? "#00f" : l.color === 6 ? "#f0f" : "#888" }} />
                      <span className="text-slate-400">{l.name}</span>
                      {l.frozen && <EyeOff size={10} className="text-slate-600" />}
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2">
                <button onClick={() => { setRenameTarget(selectedFile); setRenameValue(selectedFile.replace(/\.dxf$/i, "")); }} className="flex-1 flex items-center justify-center gap-1 px-3 py-2 rounded-xl border border-white/10 text-xs text-slate-400 hover:text-white">
                  <Pencil size={12} /> Rename
                </button>
                <button onClick={() => setDeleteTarget(selectedFile)} className="flex-1 flex items-center justify-center gap-1 px-3 py-2 rounded-xl border border-red-500/20 text-xs text-red-400 hover:bg-red-500/10">
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Create DXF Dialog */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowCreate(false)}>
          <div className="bg-[#0f0f12] border border-white/10 rounded-2xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2"><Plus size={18} className="text-amber-400" /> Create DXF</h2>
              <button onClick={() => setShowCreate(false)} className="text-slate-600 hover:text-slate-300"><X size={18} /></button>
            </div>

            <div className="space-y-3">
              <label className="block text-xs text-slate-500">Filename</label>
              <input value={createName} onChange={e => setCreateName(e.target.value)} placeholder="my_floorplan.dxf" className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />

              <label className="block text-xs text-slate-500">Description (optional)</label>
              <input value={createDesc} onChange={e => setCreateDesc(e.target.value)} placeholder="A simple floor plan" className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />

              <label className="block text-xs text-slate-500">Default Layer(s) (comma-separated)</label>
              <input value={createLayers} onChange={e => setCreateLayers(e.target.value)} placeholder="walls, doors, labels" className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30" />

              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Entities</label>
                <div className="flex gap-1">
                  {(Object.keys(DEFAULT_ENTITIES) as EntityType[]).map(et => (
                    <button key={et} onClick={() => addEntity(et)} className="flex items-center gap-1 px-2 py-1 rounded-lg bg-white/5 text-xs text-slate-400 hover:text-white" title={`Add ${et}`}>
                      {(() => {
                        const Icon = ENTITY_ICONS[et];
                        return <Icon size={12} />;
                      })()}
                      {et}
                    </button>
                  ))}
                </div>
              </div>

              {createEntities.map((ent, idx) => (
                <div key={idx} className="bg-black/30 border border-white/5 rounded-xl p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className={`text-xs font-bold uppercase ${ENTITY_COLORS[ent.type]}`}>
                      {(() => {
                        const Icon = ENTITY_ICONS[ent.type];
                        return <Icon size={12} className="inline mr-1" />;
                      })()} {ent.type}
                    </span>
                    <button onClick={() => removeEntity(idx)} className="text-slate-600 hover:text-red-400"><X size={12} /></button>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {ent.type === "line" && (
                      <>
                        <input type="number" placeholder="x1" value={ent.x1 ?? 0} onChange={e => updateEntity(idx, { x1: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="y1" value={ent.y1 ?? 0} onChange={e => updateEntity(idx, { y1: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="x2" value={ent.x2 ?? 100} onChange={e => updateEntity(idx, { x2: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="y2" value={ent.y2 ?? 0} onChange={e => updateEntity(idx, { y2: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                      </>
                    )}
                    {ent.type === "rect" && (
                      <>
                        <input type="number" placeholder="x" value={ent.x ?? 0} onChange={e => updateEntity(idx, { x: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="y" value={ent.y ?? 0} onChange={e => updateEntity(idx, { y: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="width" value={ent.w ?? 100} onChange={e => updateEntity(idx, { w: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="height" value={ent.h ?? 80} onChange={e => updateEntity(idx, { h: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                      </>
                    )}
                    {ent.type === "circle" && (
                      <>
                        <input type="number" placeholder="cx" value={ent.cx ?? 50} onChange={e => updateEntity(idx, { cx: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="cy" value={ent.cy ?? 50} onChange={e => updateEntity(idx, { cy: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="radius" value={ent.r ?? 30} onChange={e => updateEntity(idx, { r: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <div />
                      </>
                    )}
                    {ent.type === "text" && (
                      <>
                        <input type="number" placeholder="x" value={ent.x ?? 10} onChange={e => updateEntity(idx, { x: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="number" placeholder="y" value={ent.y ?? 10} onChange={e => updateEntity(idx, { y: parseFloat(e.target.value) || 0 })} className="bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                        <input type="text" placeholder="Text content" value={ent.content ?? "Label"} onChange={e => updateEntity(idx, { content: e.target.value })} className="col-span-2 bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-slate-200 outline-none" />
                      </>
                    )}
                    {ent.type === "polyline" && (
                      <div className="col-span-2 text-xs text-slate-500">
                        {ent.points?.length} points
                        <button onClick={() => updateEntity(idx, { points: [...(ent.points || []), [0, 0]] })} className="ml-2 text-amber-400 hover:underline">+ Add point</button>
                      </div>
                    )}
                  </div>
                  <input type="text" placeholder="layer" value={ent.layer || ""} onChange={e => updateEntity(idx, { layer: e.target.value })} className="w-full bg-black/40 border border-white/5 rounded-lg px-2 py-1 text-xs text-slate-400 outline-none" />
                </div>
              ))}
            </div>

            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowCreate(false)} className="flex-1 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white">Cancel</button>
              <button onClick={handleCreate} disabled={creating || !createName} className="flex-1 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm font-bold flex items-center justify-center gap-2">
                {creating ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                {creating ? "Creating..." : "Create DXF"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Dialog */}
      {renameTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setRenameTarget(null)}>
          <div className="bg-[#0f0f12] border border-white/10 rounded-2xl p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-white mb-4">Rename File</h2>
            <input value={renameValue} onChange={e => setRenameValue(e.target.value)} placeholder="New filename" className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500/30 mb-4" />
            <p className="text-xs text-slate-600 mb-4">.dxf extension will be added automatically if omitted.</p>
            <div className="flex gap-3">
              <button onClick={() => setRenameTarget(null)} className="flex-1 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white">Cancel</button>
              <button onClick={handleRename} disabled={!renameValue} className="flex-1 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm font-bold">Rename</button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setDeleteTarget(null)}>
          <div className="bg-[#0f0f12] border border-white/10 rounded-2xl p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center"><AlertTriangle size={20} className="text-red-400" /></div>
              <div>
                <h2 className="text-lg font-bold text-white">Delete File</h2>
                <p className="text-sm text-slate-400">This action cannot be undone.</p>
              </div>
            </div>
            <p className="text-sm text-slate-300 mb-4">Are you sure you want to delete <strong className="text-white">{deleteTarget}</strong>?</p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteTarget(null)} className="flex-1 py-2.5 rounded-xl border border-white/10 text-sm text-slate-400 hover:text-white">Cancel</button>
              <button onClick={handleDelete} className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-sm font-bold flex items-center justify-center gap-2">
                <Trash2 size={14} /> Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
