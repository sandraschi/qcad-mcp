import { CheckCircle, Code2, Download, ExternalLink, FileCode, Loader2, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface ScriptResult {
	title: string;
	source: string;
	url: string;
	description: string;
	category: string;
}

const SOURCES = [
	{ key: "all", label: "All Sources", color: "bg-amber-600" },
	{ key: "gallery", label: "Curated Gallery", color: "bg-emerald-600" },
	{ key: "gist", label: "GitHub Gist", color: "bg-blue-600" },
	{ key: "examples", label: "QCAD Examples", color: "bg-purple-600" },
];

export default function ScriptsPage() {
	const [source, setSource] = useState("all");
	const [query, setQuery] = useState("");
	const [category, setCategory] = useState("");
	const [categories, setCategories] = useState<{ id: string; label: string }[]>([]);
	const [results, setResults] = useState<ScriptResult[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");
	const [downloading, setDownloading] = useState<string | null>(null);
	const [recent, setRecent] = useState<string[]>([]);

	useEffect(() => {
		fetch(API_BASE + "/api/v1/scripts/categories")
			.then((r) => r.json())
			.then((j) => {
				if (j.categories) setCategories(j.categories);
			})
			.catch(() => {});
	}, []);

	const search = async () => {
		setLoading(true);
		setError("");
		setResults([]);
		try {
			const params = new URLSearchParams();
			if (query.trim()) params.set("query", query.trim());
			if (category) params.set("category", category);
			if (source !== "all") params.set("source", source);
			params.set("limit", "20");
			const r = await fetch(API_BASE + `/api/v1/scripts/search?${params}`);
			const j = await r.json();
			if (j.success) setResults(j.results);
			else setError(j.error || "Search failed");
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setLoading(false);
		}
	};

	// biome-ignore lint/correctness/useExhaustiveDependencies: auto-search on source change only
	useEffect(() => {
		search();
	}, [source]);

	const downloadScript = async (item: ScriptResult) => {
		if (!item.url && item.source !== "gallery") {
			window.open("https://gist.github.com/search?q=qcad", "_blank", "noopener");
			return;
		}
		setDownloading(item.title);
		try {
			const r = await fetch(API_BASE + "/api/v1/scripts/download", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					title: item.title,
					source: item.source,
					url: item.url || "",
				}),
			});
			const j = await r.json();
			if (j.success) {
				setRecent((prev) => [j.filename, ...prev].slice(0, 5));
				setError("");
			} else setError(j.error || "Download failed");
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : String(e));
		} finally {
			setDownloading(null);
		}
	};

	const sourceColor = (s: string) => {
		if (s === "gallery") return "text-emerald-400";
		if (s === "gist") return "text-blue-400";
		if (s === "examples") return "text-purple-400";
		return "text-slate-400";
	};

	return (
		<div className="max-w-6xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<FileCode className="text-amber-400" /> ECMAScript Library
			</h1>
			<p className="text-sm text-slate-300">
				Browse curated QCAD scripts, QCAD bundled examples, and GitHub Gists. Download to the depot and use with{" "}
				<code className="text-amber-400">plan_script</code>.
			</p>

			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-4">
				<div className="flex flex-wrap gap-2">
					{SOURCES.map((s) => (
						<button
							type="button"
							key={s.key}
							onClick={() => setSource(s.key)}
							className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${source === s.key ? `${s.color} text-white shadow-lg` : "bg-white/10 text-slate-400 hover:bg-white/10"}`}
						>
							{s.label}
						</button>
					))}
				</div>

				<div className="flex gap-2">
					<div className="flex-1 relative">
						<Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300" />
						<input
							type="text"
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							onKeyDown={(e) => e.key === "Enter" && search()}
							placeholder="Search scripts (e.g. dimension, hatch, room)..."
							className="w-full pl-10 pr-4 py-2.5 bg-white/10 border border-white/10 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
						/>
					</div>
					<button
						type="button"
						onClick={search}
						disabled={loading}
						className="px-6 py-2.5 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 text-white rounded-xl text-sm font-bold flex items-center gap-2"
					>
						{loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />} Search
					</button>
				</div>

				{categories.length > 0 && (
					<div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto">
						{categories.map((c) => (
							<button
								type="button"
								key={c.id}
								onClick={() => setCategory(c.id === category ? "" : c.id)}
								className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-all ${category === c.id ? "bg-amber-600 text-white shadow-lg" : "bg-white/10 text-slate-300 hover:text-slate-300 hover:bg-white/10"}`}
							>
								{c.label}
							</button>
						))}
					</div>
				)}

				{error && <p className="text-red-400 text-sm">{error}</p>}
			</div>

			{results.length > 0 && <p className="text-slate-300 text-sm">{results.length} scripts found</p>}

			<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
				{results.map((item, i) => (
					<div
						key={`${item.title}-${i}`}
						className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden hover:border-amber-500/30 transition-all"
					>
						<div className="p-4 space-y-2">
							<div className="flex items-start gap-2">
								<Code2 size={16} className={`mt-0.5 shrink-0 ${sourceColor(item.source)}`} />
								<div className="min-w-0">
									<h3 className="text-sm font-bold text-white leading-tight">{item.title}</h3>
									<p className="text-xs text-slate-400 mt-1 line-clamp-2">{item.description}</p>
								</div>
							</div>
							<div className="flex items-center gap-2 text-xs">
								<span className={`px-2 py-0.5 rounded uppercase font-bold ${sourceColor(item.source)} bg-white/5`}>
									{item.source}
								</span>
								{item.category && <span className="text-slate-500">{item.category}</span>}
							</div>
							<div className="flex items-center gap-2 pt-1">
								<button
									type="button"
									onClick={() => downloadScript(item)}
									disabled={downloading === item.title}
									className="flex items-center gap-1 px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/40 disabled:opacity-30 text-amber-400 rounded-lg text-sm font-bold transition-all"
								>
									{downloading === item.title ? (
										<Loader2 size={12} className="animate-spin" />
									) : (
										<>
											<Download size={12} /> Add to Depot
										</>
									)}
								</button>
								{item.url && !item.url.startsWith("gallery://") && (
									<a
										href={item.url}
										target="_blank"
										rel="noopener noreferrer"
										className="text-slate-400 hover:text-slate-400"
									>
										<ExternalLink size={14} />
									</a>
								)}
							</div>
						</div>
					</div>
				))}
			</div>

			{!loading && results.length === 0 && !error && (
				<div className="text-center py-12 text-slate-400">
					<FileCode size={48} className="mx-auto mb-4 opacity-30" />
					<p>
						Search for QCAD ECMAScript scripts. The curated gallery has ready-to-use drawing, dimension, and utility
						scripts.
					</p>
				</div>
			)}

			{recent.length > 0 && (
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 space-y-2">
					<h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
						<CheckCircle size={12} className="text-emerald-400" /> Added to Depot
					</h3>
					{recent.map((f) => (
						<div key={f} className="flex items-center gap-2 p-2 rounded-xl bg-white/10 text-sm text-slate-300">
							<Download size={14} className="text-emerald-400 shrink-0" />
							<span className="truncate">{f}</span>
							<a href={`/api/v1/depot/${f}`} className="text-sm text-amber-400 ml-auto shrink-0">
								View in Depot →
							</a>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
