import { Box, CheckCircle, Cpu, Loader2, Settings, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import { llmAvailable, useLlm } from "../store/llm";

export default function SettingsPage() {
	const [ollamaUrl, setOllamaUrl] = useState("http://127.0.0.1:11434");
	const [model, setModel] = useState("");
	const [qcadProPath, setQcadProPath] = useState("");
	const [wallHeight, setWallHeight] = useState(3.0);
	const [wallThickness, setWallThickness] = useState(0.3);
	const [status, setStatus] = useState("");

	// Global LLM state (Zustand) — single source of truth fleet-wide.
	const providers = useLlm((s) => s.providers);
	const selectedProvider = useLlm((s) => s.selectedProvider);
	const selectedModel = useLlm((s) => s.selectedModel);
	const loaded = useLlm((s) => s.loaded);
	const gpus = useLlm((s) => s.gpus);
	const probing = useLlm((s) => s.probing);
	const probed = useLlm((s) => s.probed);
	const probeAll = useLlm((s) => s.probeAll);
	const refreshTelemetry = useLlm((s) => s.refreshTelemetry);
	const selectProvider = useLlm((s) => s.selectProvider);
	const selectModel = useLlm((s) => s.selectModel);
	const [unloading, setUnloading] = useState(false);

	const selectedEndpoint = providers.find((p) => p.name === selectedProvider)?.endpoint ?? "";
	const availableModels = providers.find((p) => p.name === selectedProvider)?.models ?? [];
	const providerDetected = providers.some((p) => p.name === selectedProvider && p.status === "detected");

	useEffect(() => {
		void probeAll();
	}, [probeAll]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: intentional re-run on provider change; refreshTelemetry reads the selection via get().
	useEffect(() => {
		void refreshTelemetry();
	}, [refreshTelemetry, selectedProvider]);

	const save = async () => {
		setStatus("Saving...");
		try {
			const r = await fetch(API_BASE + "/api/v1/settings", {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					ollama_url: selectedEndpoint || ollamaUrl,
					model: selectedModel || model,
					qcad_pro_path: qcadProPath,
					default_wall_height: wallHeight,
					default_wall_thickness: wallThickness,
				}),
			});
			const j = await r.json();
			const sw = j.llm_switch;
			if (sw?.engine) {
				const ev = (sw.evicted || []).join(", ") || "none";
				setStatus(`Saved. Evicted: ${ev} / warmed: ${sw.warmed ? selectedModel : "nothing"}.`);
			} else if (selectedModel) {
				setStatus("Saved (LLM engine unreachable - config stored, VRAM untouched).");
			} else {
				setStatus("Saved.");
			}
			void refreshTelemetry();
		} catch {
			setStatus("Error saving.");
		}
	};

	const unloadAll = async () => {
		if (!selectedEndpoint) return;
		setUnloading(true);
		try {
			await fetch(API_BASE + "/api/llm/unload", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					provider: "ollama",
					endpoint: selectedEndpoint,
				}),
			});
			setStatus("Unloaded all resident models.");
			void refreshTelemetry();
		} catch {
			setStatus("Unload failed.");
		} finally {
			setUnloading(false);
		}
	};

	const detectedProviders = providers.filter((p) => p.status === "detected");

	return (
		<div className="max-w-2xl space-y-6" data-testid="settings-page">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Settings className="text-amber-400" /> Settings
			</h1>

			{/* LLM Provider */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Cpu size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">LLM Provider</h3>
				</div>

				{/* Provider detection */}
				<div className="space-y-2" data-testid="llm-provider-cards">
					<p className="text-sm text-slate-300 uppercase tracking-wider">Detection</p>
					{providers.map((p) => (
						<div key={p.name} className="flex items-center gap-3 text-sm">
							{p.status === "probing" && <Loader2 size={14} className="animate-spin text-slate-300" />}
							{p.status === "detected" && (
								<CheckCircle size={14} className="text-emerald-400" data-testid={`llm-provider-ok-${p.name}`} />
							)}
							{p.status === "not_found" && <XCircle size={14} className="text-slate-600" />}
							<span className="text-slate-200">{p.name}</span>
							<span className="text-slate-300">{p.endpoint}</span>
							<span
								className={`text-sm ${p.status === "detected" ? "text-emerald-400" : p.status === "probing" ? "text-amber-400" : "text-slate-300"}`}
							>
								{p.status === "probing" ? "Probing..." : p.status === "detected" ? "Detected" : "Not found"}
							</span>
						</div>
					))}
				</div>

				{/* GPU opportunity prompt: GPU present but no local LLM running */}
				{probed && !llmAvailable({ providers }) && gpus.length > 0 && (
					<div
						className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-slate-200"
						data-testid="llm-onboarding"
					>
						GPU detected ({gpus.map((g) => g.name).join(", ")}) but no local LLM is running. Install{" "}
						<a href="https://ollama.com" target="_blank" rel="noreferrer" className="text-amber-400 underline">
							Ollama
						</a>{" "}
						and pull a model (e.g. <code className="font-mono">ollama pull qwen3:8b</code>) to enable the AI Demo, Chat,
						and plan generation.
					</div>
				)}

				{/* Provider selector */}
				<div>
					<label htmlFor="llm-provider" className="block text-sm text-slate-200 mb-1">
						Active Provider
					</label>
					{detectedProviders.length > 0 ? (
						<select
							id="llm-provider"
							value={selectedProvider}
							onChange={(e) => selectProvider(e.target.value)}
							data-testid="llm-provider-select"
							className="w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
						>
							{detectedProviders.map((p) => (
								<option key={p.name} value={p.name}>
									{p.name} ({p.endpoint})
								</option>
							))}
						</select>
					) : (
						<div className="text-sm text-slate-300 italic bg-[#18181c] rounded-xl px-4 py-2.5 border border-white/10">
							{probing
								? "Probing for local LLM providers..."
								: "No local LLM detected. Install Ollama or LM Studio to enable AI features."}
						</div>
					)}
				</div>

				{/* Model selector */}
				{selectedProvider && providerDetected && (
					<div>
						<label htmlFor="llm-model" className="block text-sm text-slate-200 mb-1">
							Model
						</label>
						{availableModels.length > 0 ? (
							<select
								id="llm-model"
								value={selectedModel}
								onChange={(e) => selectModel(e.target.value)}
								data-testid="llm-model-select"
								className="w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
							>
								<option value="">Select a model...</option>
								{availableModels.map((m) => (
									<option key={m} value={m}>
										{m}
									</option>
								))}
							</select>
						) : (
							<div className="text-sm text-slate-300 italic bg-[#18181c] rounded-xl px-4 py-2.5 border border-white/10">
								Fetching models...
							</div>
						)}
					</div>
				)}

				{/* Legacy fallback inputs (only shown when no provider detected) */}
				{detectedProviders.length === 0 && !probing && (
					<>
						<label className="block text-sm text-slate-300">
							Ollama / LMStudio URL
							<input
								value={ollamaUrl}
								onChange={(e) => setOllamaUrl(e.target.value)}
								className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
							/>
						</label>
						<label className="block text-sm text-slate-300">
							Model
							<input
								value={model}
								onChange={(e) => setModel(e.target.value)}
								className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
							/>
						</label>
					</>
				)}
			</div>

			{/* VRAM residents + telemetry */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-3">
				<div className="flex items-center justify-between">
					<h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">Resident Models / VRAM</h3>
					<button
						type="button"
						onClick={unloadAll}
						disabled={unloading || loaded.length === 0}
						className="px-3 py-1.5 rounded-xl bg-red-600/20 hover:bg-red-600/40 disabled:opacity-40 text-red-400 text-sm font-bold"
					>
						{unloading ? "Unloading..." : "Unload all"}
					</button>
				</div>
				{loaded.length > 0 ? (
					<ul className="space-y-1 text-sm text-slate-200">
						{loaded.map((m) => (
							<li key={m.name} className="flex justify-between">
								<span>{m.name}</span>
								<span className="text-slate-300">{m.size_vram_mb} MB VRAM</span>
							</li>
						))}
					</ul>
				) : (
					<p className="text-sm text-slate-300 italic">Nothing resident — VRAM is free.</p>
				)}
				{gpus.length > 0 && (
					<ul className="space-y-1 text-sm text-slate-300">
						{gpus.map((g) => (
							<li key={g.index}>
								GPU{g.index} {g.name}: {g.used_mb}/{g.total_mb} MB used
							</li>
						))}
					</ul>
				)}
			</div>

			{/* Extrusion Defaults */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Box size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">Extrusion Defaults</h3>
				</div>
				<div className="grid grid-cols-2 gap-4">
					<label className="block text-sm text-slate-300">
						Default Wall Height (m)
						<input
							type="number"
							step="0.1"
							min="0.5"
							value={wallHeight}
							onChange={(e) => setWallHeight(Number.parseFloat(e.target.value) || 3)}
							className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
						/>
					</label>
					<label className="block text-sm text-slate-300">
						Default Wall Thickness (m)
						<input
							type="number"
							step="0.05"
							min="0.05"
							value={wallThickness}
							onChange={(e) => setWallThickness(Number.parseFloat(e.target.value) || 0.3)}
							className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
						/>
					</label>
				</div>
			</div>

			{/* QCAD Pro Path */}
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 space-y-4">
				<div className="flex items-center gap-2 mb-2">
					<Settings size={16} className="text-amber-400" />
					<h3 className="text-sm font-bold text-slate-300 uppercase tracking-wider">QCAD Pro (Optional)</h3>
				</div>
				<label className="block text-sm text-slate-300">
					Path to qcad.exe
					<input
						value={qcadProPath}
						onChange={(e) => setQcadProPath(e.target.value)}
						placeholder="C:\Program Files\QCAD\qcad.exe"
						className="mt-1 w-full bg-[#18181c] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
					/>
				</label>
				<p className="text-sm text-slate-300">
					QCAD Pro (Swiss-made, ~€50) enables dwg2pdf and dwg2svg with perfect hatches, text, and dimension rendering.
				</p>
			</div>

			<button
				type="button"
				onClick={save}
				className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-sm font-bold"
			>
				Save Settings
			</button>
			{status && <p className="text-sm text-slate-300">{status}</p>}
		</div>
	);
}
