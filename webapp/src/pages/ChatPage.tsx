import { Loader2, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import { sendLlmChat } from "../lib/llm";
import { llmAvailable, useLlm } from "../store/llm";

interface Message {
	id: number;
	role: "user" | "assistant";
	content: string;
}

let nextMessageId = 1;
const withId = (m: Omit<Message, "id">): Message => ({ ...m, id: nextMessageId++ });

interface Personality {
	id: string;
	label: string;
	prompt: string;
}

const PERSONALITIES: Personality[] = [
	{
		id: "cad-expert",
		label: "CAD Expert",
		prompt: "You are a QCAD and floor-plan expert. Answer with concrete DXF workflows, layer names, and tool calls.",
	},
	{
		id: "architect",
		label: "Architect",
		prompt: "You are a practicing architect. Discuss layouts, room programming, areas, and building code implications.",
	},
	{
		id: "engineer",
		label: "Structural Engineer",
		prompt: "You are a structural engineer. Focus on beams, loads, spans, and wall build-ups. Show numbers.",
	},
	{
		id: "teacher",
		label: "Teacher",
		prompt: "You are a patient CAD teacher. Explain step by step and name the exact buttons, pages, and tools to use.",
	},
	{ id: "concise", label: "Concise", prompt: "You are a concise assistant. Give brief, to-the-point answers." },
	{ id: "custom", label: "Custom…", prompt: "" },
];

const EXAMPLE_PROMPTS = [
	"How do I turn a floor plan DXF into a 3D-printable STL?",
	"What wall height and thickness should I use for a residential plan?",
	"My SVG preview is empty — what do I check first?",
	"Which layers should carry walls vs furniture?",
	"DWG in, DXF out — what do I need?",
	"How do I auto-dimension all walls for a BIM handoff?",
	"Explain the extrude → OBJ → Resonite path.",
];

const HISTORY_KEY = "chat_history";
const PERSONALITY_KEY = "chat_personality";
const CUSTOM_KEY = "chat_custom_prompt";

async function streamChat(model: string, prompt: string, system: string, onToken: (t: string) => void): Promise<void> {
	const r = await fetch(API_BASE + "/api/llm/chat/stream", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ provider: "ollama", model, prompt, system }),
	});
	if (!r.ok || !r.body) throw new Error(`Stream failed (HTTP ${r.status})`);
	const reader = r.body.getReader();
	const decoder = new TextDecoder();
	let buf = "";
	let gotToken = false;
	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;
		buf += decoder.decode(value, { stream: true });
		const parts = buf.split("\n\n");
		buf = parts.pop() ?? "";
		for (const part of parts) {
			const line = part.trim();
			if (!line.startsWith("data:")) continue;
			const payload = line.slice(5).trim();
			if (payload === "[DONE]") return;
			try {
				const j = JSON.parse(payload);
				if (j.error) throw new Error(j.error);
				const token: string = j.choices?.[0]?.delta?.content ?? "";
				if (token) {
					gotToken = true;
					onToken(token);
				}
			} catch (e) {
				if (e instanceof Error && e.message && !e.message.startsWith("Unexpected")) throw e;
			}
		}
	}
	if (!gotToken) throw new Error("Empty stream — falling back");
}

export default function ChatPage() {
	const [messages, setMessages] = useState<Message[]>(() => {
		try {
			const saved = localStorage.getItem(HISTORY_KEY);
			const parsed = saved ? (JSON.parse(saved) as Omit<Message, "id">[]) : [];
			return parsed.map((m) => withId({ role: m.role, content: m.content }));
		} catch {
			return [];
		}
	});
	const [input, setInput] = useState("");
	const [sending, setSending] = useState(false);
	const [personalityId, setPersonalityId] = useState(() => {
		try {
			return localStorage.getItem(PERSONALITY_KEY) || "cad-expert";
		} catch {
			return "cad-expert";
		}
	});
	const [customPrompt, setCustomPrompt] = useState(() => {
		try {
			return localStorage.getItem(CUSTOM_KEY) || "";
		} catch {
			return "";
		}
	});
	const [skillPreprompt, setSkillPreprompt] = useState("");
	const [error, setError] = useState("");
	const bottomRef = useRef<HTMLDivElement>(null);

	const providers = useLlm((s) => s.providers);
	const selectedModel = useLlm((s) => s.selectedModel);
	const probed = useLlm((s) => s.probed);
	const probeAll = useLlm((s) => s.probeAll);
	const available = llmAvailable({ providers });

	useEffect(() => {
		if (!probed) void probeAll();
	}, [probed, probeAll]);

	// Skill-first: load the domain skill once, use as system preprompt base.
	useEffect(() => {
		fetch(API_BASE + "/api/skills")
			.then((r) => r.json())
			.then((j) => {
				const skills = Array.isArray(j.skills) ? j.skills : [];
				const main = skills.find((s: { name: string }) => s.name === "qcad-cad") ?? skills[0];
				const content: string = main?.content ?? "";
				const head = content.split("\n").slice(0, 40).join("\n").slice(0, 2000);
				if (head) setSkillPreprompt(head);
			})
			.catch(() => {});
	}, []);

	useEffect(() => {
		try {
			if (messages.length > 0) localStorage.setItem(HISTORY_KEY, JSON.stringify(messages.slice(-100)));
			else localStorage.removeItem(HISTORY_KEY);
		} catch {}
	}, [messages]);

	// biome-ignore lint/correctness/useExhaustiveDependencies: scroll on new messages only; the ref is stable.
	useEffect(() => {
		bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	const persistPersonality = (id: string) => {
		setPersonalityId(id);
		try {
			localStorage.setItem(PERSONALITY_KEY, id);
		} catch {}
	};

	const systemPrompt = () => {
		const base = skillPreprompt ? `${skillPreprompt}\n\n` : "";
		if (personalityId === "custom") return `${base}${customPrompt || "You are a helpful assistant."}`;
		return `${base}${PERSONALITIES.find((p) => p.id === personalityId)?.prompt ?? ""}`;
	};

	const send = async (text: string) => {
		const prompt = text.trim();
		if (!prompt || sending) return;
		if (!selectedModel) {
			setError(
				"Pick a model first — Settings > LLM Provider, or the selector in the controls bar needs a running Ollama.",
			);
			return;
		}
		setError("");
		setMessages((prev) => [...prev, withId({ role: "user", content: prompt })]);
		setInput("");
		setSending(true);
		let acc = "";
		setMessages((prev) => [...prev, withId({ role: "assistant", content: "" })]);
		const append = (t: string) => {
			acc += t;
			const snapshot = acc;
			setMessages((prev) => {
				const next = [...prev];
				next[next.length - 1] = { ...next[next.length - 1], content: snapshot };
				return next;
			});
		};
		try {
			await streamChat(selectedModel, prompt, systemPrompt(), append);
			if (!acc) throw new Error("Empty stream — falling back");
		} catch {
			try {
				const reply = await sendLlmChat(selectedModel, prompt, systemPrompt());
				const snapshot = reply;
				setMessages((prev) => {
					const next = [...prev];
					next[next.length - 1] = { ...next[next.length - 1], content: snapshot };
					return next;
				});
			} catch (e: unknown) {
				const msg = e instanceof Error ? e.message : "Request failed. Is the backend running?";
				setMessages((prev) => {
					const next = [...prev];
					next[next.length - 1] = { ...next[next.length - 1], content: `Error: ${msg}` };
					return next;
				});
			}
		}
		setSending(false);
	};

	const exportChat = () => {
		if (messages.length === 0) return;
		const lines = messages.map((m) => `[${m.role.toUpperCase()}] ${m.content}`);
		const blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "qcad-chat.txt";
		a.click();
		URL.revokeObjectURL(url);
	};

	const clearChat = () => {
		setMessages([]);
		setError("");
	};

	return (
		<div className="max-w-4xl space-y-4" data-testid="chat-page">
			<div className="flex items-center gap-3">
				<h1 className="text-2xl font-bold text-white">CAD Chat</h1>
				<span
					className={`text-sm ${available ? "text-emerald-400" : "text-slate-300"}`}
					title={available ? `LLM ready (${selectedModel || "no model selected"})` : "No local LLM detected"}
				>
					{available ? `● ${selectedModel || "LLM ready — pick a model"}` : "○ No LLM — see Settings"}
				</span>
			</div>

			<div
				className="bg-[#1e1e26] border border-white/10 rounded-2xl p-3 flex flex-wrap items-center gap-3"
				data-testid="chat-controls"
			>
				<select
					value={personalityId}
					onChange={(e) => persistPersonality(e.target.value)}
					data-testid="personality-select"
					className="bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-sm text-slate-200 outline-none focus:border-amber-500"
				>
					{PERSONALITIES.map((p) => (
						<option key={p.id} value={p.id}>
							{p.label}
						</option>
					))}
				</select>
				{personalityId === "custom" && (
					<input
						value={customPrompt}
						onChange={(e) => {
							setCustomPrompt(e.target.value);
							try {
								localStorage.setItem(CUSTOM_KEY, e.target.value);
							} catch {}
						}}
						placeholder="Custom system prompt…"
						className="flex-1 min-w-[200px] bg-[#18181c] border border-white/10 rounded-xl px-3 py-2 text-sm text-slate-200 outline-none focus:border-amber-500"
					/>
				)}
				<div className="ml-auto flex items-center gap-2">
					<button
						type="button"
						onClick={exportChat}
						disabled={messages.length === 0}
						data-testid="chat-export"
						className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-40 text-slate-200 text-sm font-bold"
					>
						Export
					</button>
					<button
						type="button"
						onClick={clearChat}
						disabled={messages.length === 0}
						data-testid="chat-clear"
						className="px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 disabled:opacity-40 text-slate-200 text-sm font-bold"
					>
						Clear
					</button>
				</div>
			</div>

			{messages.length === 0 && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-8 text-center space-y-4">
					<p className="text-lg text-slate-200 font-bold">Ask anything about your CAD files.</p>
					<p className="text-sm text-slate-300">
						I read the qcad-cad skill first, so answers reference real tools and depot files.
					</p>
					<div className="flex flex-wrap justify-center gap-2" data-testid="example-prompts">
						{EXAMPLE_PROMPTS.map((ex) => (
							<button
								type="button"
								key={ex}
								onClick={() => setInput(ex)}
								className="bg-white/10 hover:bg-white/20 text-slate-200 text-sm px-3 py-1.5 rounded-full transition-colors"
							>
								{ex}
							</button>
						))}
					</div>
				</div>
			)}

			<div className="space-y-3" data-testid="chat-messages">
				{messages.map((m) => (
					<div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
						<div
							className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
								m.role === "user" ? "bg-amber-700 text-amber-50" : "bg-[#1e1e26] border border-white/10 text-slate-200"
							}`}
						>
							{m.content || <span className="animate-pulse text-slate-300">Thinking…</span>}
						</div>
					</div>
				))}
				<div ref={bottomRef} />
			</div>

			{error && <p className="text-sm text-red-400">{error}</p>}

			<div className="flex gap-2">
				<input
					value={input}
					onChange={(e) => setInput(e.target.value)}
					onKeyDown={(e) => e.key === "Enter" && void send(input)}
					placeholder="Ask about floor plans, extrusion, layers…"
					data-testid="chat-input"
					className="flex-1 bg-[#1e1e26] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
				/>
				<button
					type="button"
					onClick={() => void send(input)}
					disabled={sending || !input.trim()}
					data-testid="chat-send"
					className="px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white text-sm font-bold flex items-center gap-2"
				>
					{sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
					Send
				</button>
			</div>
		</div>
	);
}
