import { API_BASE } from "./api";

// LLM selection sync (fleet SETTINGS_LLM rules 1-2, adapted from the
// templates/llm/lib-llm.ts contract into qcad's own client).
// Backend settings file is the single truth; localStorage is a fast-boot
// mirror. saveSelection broadcasts same-tab (the "storage" event alone
// misses same-tab writes).

const PROVIDER_KEY = "llm_provider";
const MODEL_KEY = "llm_model";
const SELECTION_EVENT = "llm-selection-changed";

export interface Selection {
	provider: string;
	model: string;
}

function storageGet(key: string): string | null {
	try {
		return localStorage.getItem(key);
	} catch {
		return null;
	}
}

function storageSet(key: string, value: string) {
	try {
		localStorage.setItem(key, value);
	} catch {
		/* quota */
	}
}

export function loadSelection(): Selection {
	return {
		provider: storageGet(PROVIDER_KEY) || "",
		model: storageGet(MODEL_KEY) || "",
	};
}

export function saveSelection(provider: string, model: string) {
	storageSet(PROVIDER_KEY, provider);
	storageSet(MODEL_KEY, model);
	try {
		window.dispatchEvent(new CustomEvent(SELECTION_EVENT, { detail: { provider, model } }));
	} catch {
		/* non-DOM */
	}
}

/** Live-sync hook: fires when any tab/page saves a new LLM selection. */
export function subscribeSelection(cb: (sel: Selection) => void): () => void {
	const onStorage = (e: StorageEvent) => {
		if (e.key === PROVIDER_KEY || e.key === MODEL_KEY) cb(loadSelection());
	};
	const onCustom = (e: Event) => {
		const d = (e as CustomEvent).detail as Selection | undefined;
		if (d && typeof d.provider === "string" && typeof d.model === "string")
			cb({ provider: d.provider, model: d.model });
	};
	window.addEventListener("storage", onStorage);
	window.addEventListener(SELECTION_EVENT, onCustom);
	return () => {
		window.removeEventListener("storage", onStorage);
		window.removeEventListener(SELECTION_EVENT, onCustom);
	};
}

export async function fetchLlmModels(endpoint: string): Promise<string[]> {
	try {
		const r = await fetch(`${endpoint}/api/tags`, {
			signal: AbortSignal.timeout(5000),
		});
		const j = await r.json();
		return (j.models || []).map((m: { name: string }) => m.name);
	} catch {
		return [];
	}
}

export async function sendLlmChat(model: string, prompt: string, system?: string): Promise<string> {
	const r = await fetch(API_BASE + "/api/llm/chat", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ provider: "ollama", model, prompt, system }),
	});
	const data = await r.json();
	if (data.response) return data.response;
	throw new Error(data.error || "No response");
}
