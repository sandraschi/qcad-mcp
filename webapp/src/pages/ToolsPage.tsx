import { ArrowUpRight, Loader2, Search, Wrench } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../lib/api";

interface ApiTool {
	name: string;
	description: string;
	ops: string[];
	params: string[];
}

export default function ToolsPage() {
	const [tools, setTools] = useState<ApiTool[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [query, setQuery] = useState("");

	useEffect(() => {
		fetch(API_BASE + "/api/tools")
			.then((r) => r.json())
			.then((j) => setTools(Array.isArray(j.tools) ? j.tools : []))
			.catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load tools"))
			.finally(() => setLoading(false));
	}, []);

	const filtered = useMemo(() => {
		const q = query.trim().toLowerCase();
		if (!q) return tools;
		return tools.filter(
			(t) =>
				t.name.toLowerCase().includes(q) ||
				t.description.toLowerCase().includes(q) ||
				t.ops.some((o) => o.toLowerCase().includes(q)),
		);
	}, [tools, query]);

	return (
		<div className="max-w-5xl space-y-6" data-testid="tools-page">
			<div className="flex items-center gap-3">
				<Wrench className="text-amber-400" size={22} />
				<h1 className="text-2xl font-bold text-white">MCP Tools</h1>
				<span className="text-sm text-slate-300" data-testid="tools-count">
					{tools.length} tools
				</span>
			</div>
			<p className="text-sm text-slate-300">
				Every operation the AI assistant can call. Each card lists its op discriminator values — try any of them live in
				the Playground.
			</p>

			<div className="relative">
				<Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300" />
				<input
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					placeholder="Search tools or ops…"
					data-testid="search-tools"
					className="w-full bg-[#1e1e26] border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
				/>
			</div>

			{loading && (
				<p className="text-sm text-slate-300 flex items-center gap-2">
					<Loader2 size={14} className="animate-spin" /> Loading tools…
				</p>
			)}
			{error && <p className="text-sm text-red-400">{error}</p>}
			{!loading && filtered.length === 0 && <p className="text-sm text-slate-300 italic">No tools match “{query}”.</p>}

			<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
				{filtered.map((t) => (
					<div key={t.name} className="bg-[#1e1e26] border border-white/10 rounded-2xl p-5 space-y-3">
						<div className="flex items-center gap-2">
							<code className="text-amber-400 font-bold text-sm font-mono">{t.name}</code>
							<Link
								to={`/playground?tool=${encodeURIComponent(t.name)}`}
								className="ml-auto flex items-center gap-1 text-sm text-slate-300 hover:text-white"
							>
								Try <ArrowUpRight size={14} />
							</Link>
						</div>
						{t.description && <p className="text-sm text-slate-300">{t.description}</p>}
						{t.ops.length > 0 && (
							<div className="flex flex-wrap gap-1.5">
								{t.ops.map((o) => (
									<code key={o} className="text-sm font-mono bg-white/10 text-slate-200 rounded-lg px-2 py-0.5">
										op=“{o}”
									</code>
								))}
							</div>
						)}
						{t.params.length > 0 && <p className="text-sm text-slate-300 font-mono">params: {t.params.join(", ")}</p>}
					</div>
				))}
			</div>
		</div>
	);
}
