import { CheckCircle, Download, ExternalLink, Grid3X3, Loader2, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface BlockResult {
	title: string;
	source: string;
	url: string;
	image_url: string;
	category: string;
}

const SOURCES = [
	{ key: "all", label: "All Sources", color: "bg-amber-600" },
	{ key: "gallery", label: "Sample Plans", color: "bg-emerald-600" },
	{ key: "cadblocksfree", label: "cadblocksfree", color: "bg-blue-600" },
	{ key: "biblocad", label: "biblocad", color: "bg-slate-600" },
];

export default function BlocksPage() {
	const [source, setSource] = useState("all");
	const [query, setQuery] = useState("");
	const [category, setCategory] = useState("");
	const [categories, setCategories] = useState<{ id: string; label: string }[]>([]);
	const [results, setResults] = useState<BlockResult[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState("");
	const [downloading, setDownloading] = useState<string | null>(null);
	const [recent, setRecent] = useState<string[]>([]);

	useEffect(() => {
		fetch(API_BASE + "/api/v1/blocks/categories")
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
			const r = await fetch(API_BASE + `/api/v1/blocks/search?${params}`);
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

	const downloadBlock = async (item: BlockResult) => {
		if (!item.url) {
			window.open("https://www.cadblocksfree.com/en/cad-blocks/", "_blank", "noopener");
			return;
		}
		setDownloading(item.title);
		try {
			const r = await fetch(API_BASE + "/api/v1/blocks/download", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					title: item.title,
					source: item.source,
					url: item.url,
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

	return (
		<div className="max-w-6xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<Grid3X3 className="text-amber-400" /> CAD Blocks
			</h1>

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
							placeholder="Search CAD blocks..."
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
								className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-all ${category === c.id ? "bg-amber-600 text-white shadow-lg" : c.id === "" ? "bg-white/10 text-slate-400 hover:bg-white/10" : "bg-white/10 text-slate-300 hover:text-slate-300 hover:bg-white/10"}`}
							>
								{c.label}
							</button>
						))}
					</div>
				)}

				{error && <p className="text-red-400 text-sm">{error}</p>}
			</div>

			{results.length > 0 && <p className="text-slate-300 text-sm">{results.length} blocks found</p>}

			<div className="grid grid-cols-3 gap-4">
				{results.map((item, i) => (
					<div
						key={`${item.title}-${i}`}
						className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden hover:border-amber-500/30 transition-all"
					>
						<div className="h-32 bg-[#1a1a1f] flex items-center justify-center overflow-hidden">
							{item.image_url ? (
								<img src={item.image_url} alt={item.title} className="w-full h-full object-cover" loading="lazy" />
							) : (
								<Grid3X3 size={36} className="text-slate-700" />
							)}
						</div>
						<div className="p-3 space-y-1.5">
							<h3 className="text-sm font-bold text-white line-clamp-2 leading-tight">{item.title}</h3>
							<div className="flex items-center gap-2 text-sm">
								{item.source !== "gallery" && (
									<span className="px-2 py-0.5 rounded bg-white/10 text-slate-300 uppercase">{item.source}</span>
								)}
								{item.category && <span className="text-slate-400">{item.category}</span>}
							</div>
							<div className="flex items-center gap-2 pt-1">
								<button
									type="button"
									onClick={() => downloadBlock(item)}
									disabled={downloading === item.title}
									className="flex items-center gap-1 px-3 py-1.5 bg-amber-600/20 hover:bg-amber-600/40 disabled:opacity-30 text-amber-400 rounded-lg text-sm font-bold transition-all"
								>
									{downloading === item.title ? (
										<Loader2 size={12} className="animate-spin" />
									) : item.url ? (
										<>
											<Download size={12} /> Add to Depot
										</>
									) : (
										"Browse ↗"
									)}
								</button>
								{item.url && (
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
					<Grid3X3 size={48} className="mx-auto mb-4 opacity-30" />
					<p>Search for architectural blocks, furniture, doors, or sample floor plans.</p>
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
