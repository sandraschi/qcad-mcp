import { BookOpen, Loader2, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "../lib/api";

interface Skill {
	name: string;
	path: string;
	content: string;
	description: string;
}

function parseDescription(content: string): string {
	const m = content.match(/^---\s*\n([\s\S]*?)\n---/);
	if (!m) return "";
	const dm = m[1].match(/^description:\s*(.+)$/m);
	return (dm?.[1] ?? "").trim();
}

export default function SkillsPage() {
	const [skills, setSkills] = useState<Skill[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [query, setQuery] = useState("");
	const [open, setOpen] = useState<string | null>(null);

	useEffect(() => {
		fetch(API_BASE + "/api/skills")
			.then((r) => r.json())
			.then((j) => {
				const list = Array.isArray(j.skills) ? j.skills : [];
				setSkills(
					list.map((s: { name: string; path: string; content: string }) => ({
						name: s.name,
						path: s.path,
						content: s.content,
						description: parseDescription(s.content),
					})),
				);
			})
			.catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load skills"))
			.finally(() => setLoading(false));
	}, []);

	const filtered = useMemo(() => {
		const q = query.trim().toLowerCase();
		if (!q) return skills;
		return skills.filter(
			(s) =>
				s.name.toLowerCase().includes(q) ||
				s.description.toLowerCase().includes(q) ||
				s.content.toLowerCase().includes(q),
		);
	}, [skills, query]);

	return (
		<div className="max-w-4xl space-y-6" data-testid="skills-page">
			<div className="flex items-center gap-3">
				<BookOpen className="text-amber-400" size={22} />
				<h1 className="text-2xl font-bold text-white">Agent Skills</h1>
				<span className="text-sm text-slate-300" data-testid="skills-count">
					{skills.length} skill{skills.length !== 1 ? "s" : ""}
				</span>
			</div>
			<p className="text-sm text-slate-300">
				The same skill files the Chat page loads as its system preprompt. Agents read these to drive MCP tools
				correctly.
			</p>

			<div className="relative">
				<Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300" />
				<input
					value={query}
					onChange={(e) => setQuery(e.target.value)}
					placeholder="Search skills…"
					data-testid="search-skills"
					className="w-full bg-[#1e1e26] border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-200 outline-none focus:border-amber-500"
				/>
			</div>

			{loading && (
				<p className="text-sm text-slate-300 flex items-center gap-2">
					<Loader2 size={14} className="animate-spin" /> Loading skills…
				</p>
			)}
			{error && <p className="text-sm text-red-400">{error}</p>}
			{!loading && filtered.length === 0 && <p className="text-sm text-slate-300 italic">No skills match “{query}”.</p>}

			<div className="space-y-3">
				{filtered.map((s) => (
					<div key={s.name} className="bg-[#1e1e26] border border-white/10 rounded-2xl overflow-hidden">
						<button
							type="button"
							onClick={() => setOpen(open === s.name ? null : s.name)}
							className="w-full text-left px-5 py-4 flex items-center gap-3 hover:bg-white/5"
						>
							<div className="flex-1">
								<p className="text-sm font-bold text-white font-mono">{s.name}</p>
								{s.description && <p className="text-sm text-slate-300 mt-0.5">{s.description}</p>}
								<p className="text-sm text-slate-300 font-mono mt-0.5">{s.path}</p>
							</div>
							<span className="text-slate-300 text-sm">{open === s.name ? "▾" : "▸"}</span>
						</button>
						{open === s.name && (
							<pre className="mx-4 mb-4 p-4 text-xs font-mono text-slate-300 bg-black/40 rounded-xl overflow-auto max-h-[420px] whitespace-pre-wrap">
								{s.content}
							</pre>
						)}
					</div>
				))}
			</div>
		</div>
	);
}
