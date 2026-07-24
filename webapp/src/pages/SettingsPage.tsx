import { Box, CheckCircle, Cpu, Loader2, Settings, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface ProviderInfo {
	name: string;
	port: number;
	base: string;
}

const PROVIDERS: ProviderInfo[] = [
	{ name: "Ollama", port: 11434, base: "http://127.0.0.1" },
	{ name: "LM Studio", port: 1234, base: "http://127.0.0.1" },
	{ name: "vLLM", port: 8000, base: "http://127.0.0.1" },
];

async function probeProvider(p: ProviderInfo): Promise<"detected" | "not_found"> {
	try {
		const probe = p.name === "Ollama"
			? await fetch(`${p.base}:${p.port}/api/tags`, { signal: AbortSignal.timeout(3000) })
			: await fetch(`${p.base}:${p.port}/v1/models`, { signal: AbortSignal.timeout(3000) });
		return probe.ok ? "detected" : "not_found";
	} catch { return "not_found"; }
}

async function fetchModels(p: ProviderInfo): Promise<string[]> {
	try {
		if (p.name === "Ollama") {
			const r = await fetch(`${p.base}:${p.port}/api/tags`, { signal: AbortSignal.timeout(5000) });
			const j = await r.json();
			return (j.models || []).map((m: { name: string }) => m.name);
		}
		const r = await fetch(`${p.base}:${p.port}/v1/models`, { signal: AbortSignal.timeout(5000) });
		const j = await r.json();
		return (j.data || []).map((m: { id: string }) => m.id);
	} catch { return []; }
}

export default function SettingsPage() {
	const [ollamaUrl, setOllamaUrl] = useState("http://192.168.1.11:11434");
	const [model, setModel] = useState("gemma3:1b");
	const [qcadProPath, setQcadProPath] = useState("");
	const [wallHeight, setWallHeight] = useState(3.0);
	const [wallThickness, setWallThickness] = useState(0.3);
	const [status, setStatus] = useState("");

	// LLM provider detection
	const [providerStatus, setProviderStatus] = useState<Record<string, "probing" | "detected" | "not_found">>({});
	const [selectedProvider, setSelectedProvider] = useState(() => localStorage.getItem("llm_provider") || "");
	const [availableModels, setAvailableModels] = useState<string[]>([]);
	const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem("llm_model") || "");
	const [probing, setProbing] = useState(true);

	// Probe all providers on mount
	useEffect(() => {
		const results: Record<string, "probing" | "detected" | "not_found"> = {};
		PROVIDERS.forEach((p) => { results[p.name] = "probing"; });
		setProviderStatus({ ...results });

		Promise.all(PROVIDERS.map(async (p) => {
			const r = await probeProvider(p);
			results[p.name] = r;
			setProviderStatus({ ...results });
		})).then(() => {
			setProbing(false);
			if (!selectedProvider) {
				const first = PROVIDERS.find((p) => results[p.name] === "detected");
				if (first) setSelectedProvider(first.name);
			}
		});
	}, []);

	// Fetch models when provider changes
	useEffect(() => {
		if (!selectedProvider) return;
		const p = PROVIDERS.find((pr) => pr.name === selectedProvider);
		if (!p || providerStatus[p.name] !== "detected") return;
		fetchModels(p).then((models) => {
			setAvailableModels(models);
			if (models.length > 0 && !selectedModel) {
				setSelectedModel(models[0]);
				localStorage.setItem("llm_model", models[0]);
			}
		});
	}, [selectedProvider, providerStatus]);

	const handleProviderChange = useCallback((name: string) => {
		setSelectedProvider(name);
		setSelectedModel("");
		setAvailableModels([]);
		localStorage.setItem("llm_provider", name);
		localStorage.removeItem("llm_model");
	}, []);

	const handleModelChange = useCallback((m: string) => {
		setSelectedModel(m);
		localStorage.setItem("llm_model", m);
	}, []);

	const save = async () => {
		setStatus("Saving...");
		try {
			await fetch(API_BASE + "/api/v1/settings", {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ ollama_url: ollamaUrl, model, qcad_pro_path: qcadProPath, default_wall_height: wallHeight, default_wall_thickness: wallThickness }),
			});
			setStatus("Saved.");
		} catch { setStatus("Error saving."); }
	};

	const detectedProviders = PROVIDERS.filter((p) => providerStatus[p.name] === "detected");

	return (
		<div className="max-w-2xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Settings className="text-amber-400" /> Settings
			</h1>

			{/* LLM Provider */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Cpu size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">LLM Provider</h3>
				</div>

				{/* Provider detection */}
				<div className="space-y-2">
					<p className="text-xs text-slate-500 uppercase tracking-wider">Detection</p>
					{PROVIDERS.map((p) => (
						<div key={p.name} className="flex items-center gap-3 text-sm">
							{providerStatus[p.name] === "probing" && <Loader2 size={14} className="animate-spin text-slate-400" />}
							{providerStatus[p.name] === "detected" && <CheckCircle size={14} className="text-emerald-400" />}
							{providerStatus[p.name] === "not_found" && <XCircle size={14} className="text-slate-600" />}
							<span className="text-slate-300">{p.name}</span>
							<span className="text-slate-500">:{p.port}</span>
							<span className={`text-xs ${providerStatus[p.name] === "detected" ? "text-emerald-400" : providerStatus[p.name] === "probing" ? "text-amber-400" : "text-slate-600"}`}>
								{providerStatus[p.name] === "probing" ? "Probing..." : providerStatus[p.name] === "detected" ? "Detected" : "Not found"}
							</span>
						</div>
					))}
				</div>

				{/* Provider selector */}
				<div>
					<label className="block text-sm text-slate-400 mb-1">Active Provider</label>
					{detectedProviders.length > 0 ? (
						<select
							value={selectedProvider}
							onChange={(e) => handleProviderChange(e.target.value)}
							data-testid="llm-provider-select"
							className="w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
						>
							{detectedProviders.map((p) => <option key={p.name} value={p.name}>{p.name} (:{(PROVIDERS.find((pr) => pr.name === p.name) || p).port})</option>)}
						</select>
					) : (
						<div className="text-sm text-slate-500 italic bg-[#18181c] rounded-xl px-4 py-2.5 border border-white/10">
							{probing ? "Probing for local LLM providers..." : "No local LLM detected. Install Ollama or LM Studio to enable AI features."}
						</div>
					)}
				</div>

				{/* Model selector */}
				{selectedProvider && providerStatus[selectedProvider] === "detected" && (
					<div>
						<label className="block text-sm text-slate-400 mb-1">Model</label>
						{availableModels.length > 0 ? (
							<select
								value={selectedModel || availableModels[0]}
								onChange={(e) => handleModelChange(e.target.value)}
								data-testid="llm-model-select"
								className="w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
							>
								{availableModels.map((m) => <option key={m} value={m}>{m}</option>)}
							</select>
						) : (
							<div className="text-sm text-slate-500 italic bg-[#18181c] rounded-xl px-4 py-2.5 border border-white/10">Fetching models...</div>
						)}
					</div>
				)}

				{/* Legacy fallback inputs (only shown when no provider detected) */}
				{detectedProviders.length === 0 && !probing && (
					<>
						<label className="block text-sm text-slate-400">
							Ollama / LMStudio URL
							<input value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)}
								className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500" />
						</label>
						<label className="block text-sm text-slate-400">
							Model
							<input value={model} onChange={(e) => setModel(e.target.value)}
								className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500" />
						</label>
					</>
				)}
			</div>

			{/* Extrusion Defaults */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Box size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">Extrusion Defaults</h3>
				</div>
				<div className="grid grid-cols-2 gap-4">
					<label className="block text-sm text-slate-400">
						Default Wall Height (m)
						<input type="number" step="0.1" min="0.5" value={wallHeight} onChange={(e) => setWallHeight(Number.parseFloat(e.target.value) || 3)}
							className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500" />
					</label>
					<label className="block text-sm text-slate-400">
						Default Wall Thickness (m)
						<input type="number" step="0.05" min="0.05" value={wallThickness} onChange={(e) => setWallThickness(Number.parseFloat(e.target.value) || 0.3)}
							className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500" />
					</label>
				</div>
			</div>

			{/* QCAD Pro Path */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Settings size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">QCAD Pro (Optional)</h3>
				</div>
				<label className="block text-sm text-slate-400">
					Path to qcad.exe
					<input value={qcadProPath} onChange={(e) => setQcadProPath(e.target.value)} placeholder="C:\Program Files\QCAD\qcad.exe"
						className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500" />
				</label>
				<p className="text-sm text-slate-400">QCAD Pro (Swiss-made, ~€50) enables dwg2pdf and dwg2svg with perfect hatches, text, and dimension rendering.</p>
			</div>

			<button type="button" onClick={save}
				className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-sm font-bold">Save Settings</button>
			{status && <p className="text-sm text-slate-400">{status}</p>}
		</div>
	);
}
