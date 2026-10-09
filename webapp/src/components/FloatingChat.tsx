import { Download, MessageCircle, Send, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../lib/api";
import { fetchLlmModels, loadSelection, sendLlmChat, subscribeSelection } from "../lib/llm";

interface Message {
	role: "user" | "assistant";
	content: string;
}

const PERSONALITIES = [
	{ id: "helpful", label: "Helpful", prompt: "You are a helpful assistant." },
	{
		id: "expert",
		label: "Expert",
		prompt: "You are an expert technical assistant. Provide detailed, precise answers.",
	},
	{
		id: "concise",
		label: "Concise",
		prompt: "You are a concise assistant. Give brief, to-the-point answers.",
	},
];

const EXAMPLES = ["What can you do?", "Show me the current status", "Help me understand this system"];

export default function FloatingChat() {
	const [open, setOpen] = useState(false);
	const [chat, setChat] = useState<Message[]>([]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [model, setModel] = useState(() => loadSelection().model);
	const [modelList, setModelList] = useState<string[]>([]);
	const [personality, setPersonality] = useState(() => localStorage.getItem("fc_personality") || "helpful");
	const [ollamaEndpoint, setOllamaEndpoint] = useState("http://127.0.0.1:11434");
	const bottomRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		try {
			const saved = localStorage.getItem("fc_chat");
			if (saved) setChat(JSON.parse(saved));
		} catch {}
	}, []);

	useEffect(() => {
		if (chat.length > 0) {
			const trimmed = chat.length > 100 ? chat.slice(-100) : chat;
			localStorage.setItem("fc_chat", JSON.stringify(trimmed));
		} else localStorage.removeItem("fc_chat");
	}, [chat]);

	useEffect(() => {
		// Backend truth first (Settings owns it), then live models.
		// Never auto-pick: empty selection sends nothing (fleet BUG-030).
		fetch(API_BASE + "/api/v1/settings")
			.then((r) => r.json())
			.then((j) => {
				if (j.ollama_url) setOllamaEndpoint(j.ollama_url);
				const saved: string = j.model || loadSelection().model;
				if (saved) setModel(saved);
			})
			.catch(() => {});
		return subscribeSelection((sel) => {
			if (sel.model) setModel(sel.model);
		});
	}, []);

	useEffect(() => {
		if (!ollamaEndpoint) return;
		fetchLlmModels(ollamaEndpoint).then((list) => {
			setModelList(list);
			// Drop a stale selection the engine no longer has — still no auto-pick.
			setModel((m) => {
				if (m && !list.includes(m)) {
					localStorage.removeItem("llm_model");
					return "";
				}
				return m;
			});
		});
	}, [ollamaEndpoint]);

	useEffect(() => {
		// chat.length in the condition keeps the dep honest: scroll on new messages.
		if (open && chat.length >= 0) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [chat, open]);

	const sendMessage = async (text: string) => {
		// Send-time guard (fleet SETTINGS_LLM rule 6): no fallback model, ever.
		if (!model) {
			setChat((prev) => [
				...prev,
				{ role: "user", content: text },
				{
					role: "assistant",
					content: "Pick a model first - open Settings > LLM Provider, or choose one above.",
				},
			]);
			return;
		}
		setChat((prev) => [...prev, { role: "user", content: text }]);
		setLoading(true);
		try {
			const sp = PERSONALITIES.find((p) => p.id === personality);
			const reply = await sendLlmChat(model, text, sp?.prompt);
			setChat((prev) => [...prev, { role: "assistant", content: reply }]);
		} catch (e: unknown) {
			setChat((prev) => [
				...prev,
				{
					role: "assistant",
					content: e instanceof Error ? e.message : "Request failed. Is the backend running?",
				},
			]);
		}
		setLoading(false);
	};

	const handleSend = () => {
		if (!input.trim()) return;
		sendMessage(input.trim());
		setInput("");
	};

	const handleExport = () => {
		if (chat.length === 0) return;
		const lines = chat.map((m) => `[${m.role.toUpperCase()}] ${m.content}`);
		const blob = new Blob([lines.join("\n\n")], { type: "text/plain" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = "chat-export.txt";
		a.click();
		URL.revokeObjectURL(url);
	};

	const handleClear = () => {
		setChat([]);
		localStorage.removeItem("fc_chat");
	};

	return (
		<div className="fixed bottom-5 right-5 z-50" data-testid="floating-chat">
			{open ? (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl shadow-2xl w-[380px] h-[520px] flex flex-col overflow-hidden">
					<div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
						<div className="flex items-center gap-2">
							<span className="text-sm font-semibold text-slate-200">Chat</span>
						</div>
						<div className="flex items-center gap-1.5">
							<select
								className="bg-[#18181c] border border-white/10 rounded text-[10px] px-1.5 py-1 text-slate-300 max-w-[80px]"
								value={personality}
								onChange={(e) => {
									setPersonality(e.target.value);
									localStorage.setItem("fc_personality", e.target.value);
								}}
							>
								{PERSONALITIES.map((p) => (
									<option key={p.id} value={p.id}>
										{p.label}
									</option>
								))}
							</select>
							{modelList.length > 0 && (
								<select
									className="bg-[#18181c] border border-white/10 rounded text-sm px-2 py-1 text-slate-300 max-w-[140px]"
									value={model}
									onChange={(e) => {
										setModel(e.target.value);
										localStorage.setItem("llm_model", e.target.value);
									}}
								>
									<option value="">Select model...</option>
									{modelList.map((m) => (
										<option key={m} value={m}>
											{m.split(":")[0]}
										</option>
									))}
								</select>
							)}
							<button
								type="button"
								onClick={() => setOpen(false)}
								className="p-1 rounded-lg hover:bg-white/10 text-slate-300 hover:text-white transition-all"
							>
								<X size={16} />
							</button>
						</div>
					</div>
					<div className="flex-1 overflow-y-auto p-3 space-y-2 text-sm">
						{chat.length === 0 && (
							<div className="text-center pt-4">
								<p className="text-slate-300 text-sm mb-3">Ask a question.</p>
								<div className="flex flex-wrap justify-center gap-1.5" data-testid="example-prompts">
									{EXAMPLES.map((ex) => (
										<button
											type="button"
											key={ex}
											onClick={() => setInput(ex)}
											className="bg-[#18181c] hover:bg-white/10 text-slate-300 hover:text-slate-200 text-xs px-2 py-1 rounded-full border border-white/10 transition-colors"
										>
											{ex}
										</button>
									))}
								</div>
							</div>
						)}
						{chat.map((msg) => (
							<div
								key={`${msg.role}-${msg.content.slice(0, 32)}-${msg.content.length}`}
								className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
							>
								<div
									className={`max-w-[85%] rounded-xl px-3 py-2 whitespace-pre-wrap ${
										msg.role === "user" ? "bg-amber-700 text-amber-50" : "bg-[#18181c] text-slate-300"
									}`}
								>
									{msg.content}
								</div>
							</div>
						))}
						{loading && <div className="text-slate-300 text-sm animate-pulse">Thinking...</div>}
						<div ref={bottomRef} />
					</div>
					<div className="border-t border-white/10 p-3 flex flex-col gap-2">
						<div className="flex gap-2">
							<input
								className="flex-1 bg-[#18181c] border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-amber-500"
								placeholder="Ask something..."
								value={input}
								onChange={(e) => setInput(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && handleSend()}
								data-testid="floating-chat-input"
							/>
							<button
								type="button"
								onClick={handleSend}
								disabled={loading || !input.trim()}
								className="bg-amber-600 hover:bg-amber-700 disabled:bg-slate-700 text-white px-3 py-2 rounded-lg transition-all"
								data-testid="floating-chat-send"
							>
								<Send size={16} />
							</button>
						</div>
						<div className="flex justify-end gap-1.5">
							<button
								type="button"
								onClick={handleExport}
								disabled={chat.length === 0}
								className="text-slate-300 hover:text-slate-200 disabled:text-slate-700 text-xs p-1.5 rounded-lg hover:bg-white/10 transition-all"
								title="Export chat"
							>
								<Download size={14} />
							</button>
							<button
								type="button"
								onClick={handleClear}
								disabled={chat.length === 0}
								className="text-slate-300 hover:text-slate-200 disabled:text-slate-700 text-xs p-1.5 rounded-lg hover:bg-white/10 transition-all"
								title="Clear chat"
								data-testid="floating-chat-clear"
							>
								<Trash2 size={14} />
							</button>
						</div>
					</div>
				</div>
			) : (
				<button
					type="button"
					onClick={() => setOpen(true)}
					className="h-12 w-12 rounded-full bg-amber-600 hover:bg-amber-700 shadow-xl flex items-center justify-center text-white transition-all"
					title="Open chat"
				>
					<MessageCircle size={22} />
				</button>
			)}
		</div>
	);
}
