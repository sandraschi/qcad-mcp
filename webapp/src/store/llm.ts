import { create } from "zustand";
import { API_BASE } from "../lib/api";

export interface ProviderState {
	name: string;
	endpoint: string;
	modelsPath: string;
	status: "probing" | "detected" | "not_found";
	models: string[];
}

export interface LoadedEntry {
	name: string;
	size_vram_mb: number;
	expires_at: string;
}

export interface GpuEntry {
	index: number;
	name: string;
	total_mb: number;
	used_mb: number;
	free_mb: number;
}

const PROVIDER_KEY = "llm_provider";
const MODEL_KEY = "llm_model";

const PROVIDERS = [
	{ name: "Ollama", endpoint: "http://127.0.0.1:11434", modelsPath: "/api/tags" },
	{ name: "LM Studio", endpoint: "http://127.0.0.1:1234", modelsPath: "/v1/models" },
	{ name: "vLLM", endpoint: "http://127.0.0.1:8000", modelsPath: "/v1/models" },
];

function storageGet(key: string): string {
	try {
		return localStorage.getItem(key) || "";
	} catch {
		return "";
	}
}

function storageSet(key: string, value: string) {
	try {
		if (value) localStorage.setItem(key, value);
		else localStorage.removeItem(key);
	} catch {
		/* quota */
	}
}

async function probeEndpoint(p: { endpoint: string; modelsPath: string }): Promise<boolean> {
	try {
		const r = await fetch(`${p.endpoint}${p.modelsPath}`, { signal: AbortSignal.timeout(3000) });
		return r.ok;
	} catch {
		return false;
	}
}

async function fetchModelsFor(p: { endpoint: string; modelsPath: string }): Promise<string[]> {
	try {
		const r = await fetch(`${p.endpoint}${p.modelsPath}`, { signal: AbortSignal.timeout(5000) });
		const j = await r.json();
		if (Array.isArray(j.models)) return j.models.map((m: { name: string }) => m.name).filter(Boolean);
		if (Array.isArray(j.data)) return j.data.map((m: { id: string }) => m.id).filter(Boolean);
		return [];
	} catch {
		return [];
	}
}

interface LlmStore {
	providers: ProviderState[];
	selectedProvider: string;
	selectedModel: string;
	loaded: LoadedEntry[];
	gpus: GpuEntry[];
	probing: boolean;
	probed: boolean;
	probeAll: () => Promise<void>;
	refreshModels: () => Promise<void>;
	refreshTelemetry: () => Promise<void>;
	selectProvider: (name: string) => void;
	selectModel: (model: string) => void;
}

export const useLlm = create<LlmStore>()((set, get) => ({
	providers: PROVIDERS.map((p) => ({ ...p, status: "probing" as const, models: [] })),
	selectedProvider: storageGet(PROVIDER_KEY),
	selectedModel: storageGet(MODEL_KEY),
	loaded: [],
	gpus: [],
	probing: false,
	probed: false,

	probeAll: async () => {
		if (get().probing) return;
		set({ probing: true });
		const results = await Promise.all(
			PROVIDERS.map(async (p) => ({
				...p,
				status: ((await probeEndpoint(p)) ? "detected" : "not_found") as ProviderState["status"],
				models: [] as string[],
			})),
		);
		// Restore persisted selection only if that provider is actually detected.
		const saved = storageGet(PROVIDER_KEY);
		const savedDetected = results.some((p) => p.name === saved && p.status === "detected");
		const selectedProvider = savedDetected ? saved : (results.find((p) => p.status === "detected")?.name ?? "");
		set({ providers: results, selectedProvider, probing: false, probed: true });
		if (selectedProvider) await get().refreshModels();
	},

	refreshModels: async () => {
		const { providers, selectedProvider, selectedModel } = get();
		const p = providers.find((pr) => pr.name === selectedProvider && pr.status === "detected");
		if (!p) return;
		const models = await fetchModelsFor(p);
		set({
			providers: providers.map((pr) => (pr.name === p.name ? { ...pr, models } : pr)),
		});
		// Never auto-pick (fleet BUG-030); drop stale selections the engine no longer has.
		if (selectedModel && !models.includes(selectedModel)) {
			set({ selectedModel: "" });
			storageSet(MODEL_KEY, "");
		}
	},

	refreshTelemetry: async () => {
		const { selectedProvider, providers } = get();
		const endpoint = providers.find((p) => p.name === selectedProvider)?.endpoint ?? "";
		try {
			const r = await fetch(API_BASE + `/api/llm/loaded?provider=ollama&endpoint=${encodeURIComponent(endpoint)}`);
			const j = await r.json();
			if (Array.isArray(j.models)) set({ loaded: j.models });
		} catch {
			/* engine unreachable */
		}
		try {
			const r = await fetch(API_BASE + "/api/llm/gpus");
			const j = await r.json();
			if (Array.isArray(j.gpus)) set({ gpus: j.gpus });
		} catch {
			/* no telemetry */
		}
	},

	selectProvider: (name: string) => {
		set({ selectedProvider: name, selectedModel: "" });
		storageSet(PROVIDER_KEY, name);
		storageSet(MODEL_KEY, "");
		void get().refreshModels();
	},

	selectModel: (model: string) => {
		set({ selectedModel: model });
		storageSet(MODEL_KEY, model);
	},
}));

export function llmAvailable(s: Pick<LlmStore, "providers">): boolean {
	return s.providers.some((p) => p.status === "detected");
}
