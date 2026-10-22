import { CheckCheck, Eye, FileBox, Inbox, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE, toolCallBody } from "../lib/api";

interface DepotFile {
	name: string;
	size_kb: number;
	modified?: number;
}

const SEEN_KEY = "inbox_seen_ts";

function loadSeen(): number {
	try {
		return Number(localStorage.getItem(SEEN_KEY) || 0);
	} catch {
		return 0;
	}
}

export default function InboxPage() {
	const [uploads, setUploads] = useState<DepotFile[]>([]);
	const [outputs, setOutputs] = useState<DepotFile[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");
	const [preview, setPreview] = useState<Record<string, string>>({});
	const [previewing, setPreviewing] = useState<string | null>(null);
	const [seenTs, setSeenTs] = useState<number>(() => loadSeen());

	const load = useCallback(async () => {
		setLoading(true);
		setError("");
		try {
			const r = await fetch(API_BASE + "/api/v1/files");
			const j = await r.json();
			const sortByTime = (a: DepotFile, b: DepotFile) => (b.modified ?? 0) - (a.modified ?? 0);
			setUploads([...(j.uploads || [])].sort(sortByTime));
			setOutputs([...(j.outputs || [])].sort(sortByTime));
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : "Failed to load files");
		}
		setLoading(false);
	}, []);

	useEffect(() => {
		void load();
	}, [load]);

	const isDxf = (n: string) => /\.(dxf|dwg)$/i.test(n);
	const fresh = (f: DepotFile) => (f.modified ?? 0) * 1000 > seenTs && isDxf(f.name);

	const freshCount = useMemo(
		() => [...uploads, ...outputs].filter((f) => (f.modified ?? 0) * 1000 > loadSeen()).length,
		[uploads, outputs],
	);

	const markReviewed = () => {
		const now = Date.now();
		setSeenTs(now);
		try {
			localStorage.setItem(SEEN_KEY, String(now));
		} catch {}
	};

	const previewFile = async (name: string) => {
		setPreviewing(name);
		try {
			const r = await fetch(API_BASE + "/api/v1/control/tool", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(toolCallBody("plan_to_svg", { file_name: name, output_name: `_inbox_${name}.svg` })),
			});
			const j = await r.json();
			if (j.success) setPreview((p) => ({ ...p, [name]: `/api/v1/download/${j.output}?t=${Date.now()}` }));
			else setError(j.error || `Preview failed for ${name}`);
		} catch (e: unknown) {
			setError(e instanceof Error ? e.message : "Preview failed");
		}
		setPreviewing(null);
	};

	const fmtTime = (modified?: number) => {
		if (!modified) return "unknown time";
		const d = new Date(modified * 1000);
		return d.toLocaleString();
	};

	const renderRow = (f: DepotFile, kind: "depot" | "output") => (
		<div
			key={`${kind}-${f.name}`}
			className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 flex items-center gap-3"
		>
			<FileBox size={18} className="text-amber-400 shrink-0" />
			<div className="flex-1 min-w-0">
				<div className="flex items-center gap-2">
					<span className="text-sm font-bold text-white font-mono truncate">{f.name}</span>
					{fresh(f) && (
						<span className="text-sm font-bold uppercase bg-emerald-500/20 text-emerald-400 rounded px-1.5 py-0.5 shrink-0">
							New
						</span>
					)}
				</div>
				<p className="text-sm text-slate-300">
					{f.size_kb} KB · {fmtTime(f.modified)} · {kind === "depot" ? "depot file" : "generated output"}
				</p>
				{preview[f.name] && (
					<img
						src={preview[f.name]}
						alt={`Preview of ${f.name}`}
						className="mt-2 max-h-40 rounded-xl border border-white/10 bg-black/40"
					/>
				)}
			</div>
			<div className="flex flex-col gap-1.5 shrink-0">
				{isDxf(f.name) && (
					<button
						type="button"
						onClick={() => void previewFile(f.name)}
						disabled={previewing === f.name}
						className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-40 text-slate-200 text-sm font-bold"
					>
						<Eye size={14} /> {previewing === f.name ? "…" : "Preview"}
					</button>
				)}
				{isDxf(f.name) && (
					<Link
						to={`/viewer?file=${encodeURIComponent(f.name)}`}
						className="px-3 py-1.5 rounded-lg bg-amber-600/20 hover:bg-amber-600/40 text-amber-400 text-sm font-bold text-center"
					>
						Open
					</Link>
				)}
			</div>
		</div>
	);

	return (
		<div className="max-w-4xl space-y-6" data-testid="inbox-page">
			<div className="flex items-center gap-3">
				<Inbox className="text-amber-400" size={22} />
				<h1 className="text-2xl font-bold text-white">Inbox</h1>
				<span className="text-sm text-slate-300" data-testid="inbox-count">
					{freshCount} new
				</span>
				<button
					type="button"
					onClick={markReviewed}
					data-testid="inbox-mark-reviewed"
					className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 text-sm font-bold"
				>
					<CheckCheck size={14} /> Mark all reviewed
				</button>
			</div>
			<p className="text-sm text-slate-300">
				Recent depot arrivals and generated outputs, newest first. Preview a drawing inline, open it in the Viewer, or
				mark everything reviewed to clear the “new” badges.
			</p>

			{loading && (
				<p className="text-sm text-slate-300 flex items-center gap-2">
					<Loader2 size={14} className="animate-spin" /> Loading inbox…
				</p>
			)}
			{error && <p className="text-sm text-red-400">{error}</p>}

			{!loading && uploads.length === 0 && outputs.length === 0 && (
				<p className="text-sm text-slate-300 italic">Empty — upload a DXF on the Depot page to get started.</p>
			)}

			{uploads.length > 0 && (
				<div className="space-y-3">
					<h2 className="text-sm font-bold text-slate-300 uppercase tracking-wider">Depot files</h2>
					{uploads.map((f) => renderRow(f, "depot"))}
				</div>
			)}
			{outputs.length > 0 && (
				<div className="space-y-3">
					<h2 className="text-sm font-bold text-slate-300 uppercase tracking-wider">Outputs</h2>
					{outputs.slice(0, 20).map((f) => renderRow(f, "output"))}
				</div>
			)}
		</div>
	);
}
