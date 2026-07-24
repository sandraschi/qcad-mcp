import { BarChart3, Box, Database, FileText, Layers, Ruler } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";

interface StatusData {
	ezdxf_version: string;
	qcad_pro: {
		installed: boolean;
		running: boolean;
		version: string;
		install_dir: string;
	};
}

export default function Dashboard() {
	const [status, setStatus] = useState<StatusData | null>(null);
	const [files, setFiles] = useState<{ uploads: number; outputs: number }>({
		uploads: 0,
		outputs: 0,
	});

	useEffect(() => {
		fetch(API_BASE + "/api/v1/status")
			.then((r) => r.json())
			.then(setStatus)
			.catch(() => {});
		fetch(API_BASE + "/api/v1/files")
			.then((r) => r.json())
			.then((j) =>
				setFiles({
					uploads: (j.uploads || []).length,
					outputs: (j.outputs || []).length,
				}),
			)
			.catch(() => {});
	}, []);

	return (
		<div className="space-y-6" data-testid="dashboard">
			<div className="bg-gradient-to-br from-amber-500/10 to-transparent border border-amber-500/20 rounded-2xl p-6" data-testid="hero-section">
				<h1 className="text-2xl font-bold text-white">QCAD MCP</h1>
				<p className="text-slate-400 mt-1 max-w-2xl">
					Programmatic 2D CAD server &mdash; parse, analyse, modify, and export DXF/DWG
					floor plans. Extrude walls to 3D STL, detect rooms, chain with FreeCAD for
					full BIM pipelines. Powered by ezdxf with optional QCAD Pro for PDF output.
				</p>
				<div className="flex gap-4 mt-3 text-sm text-slate-500">
					<span className="flex items-center gap-1.5">
						<span className={`w-2 h-2 rounded-full ${status?.qcad_pro?.running ? "bg-green-500" : "bg-red-500"} animate-pulse`} />
						{status?.qcad_pro?.running ? `QCAD Pro ${status.qcad_pro.version}` : status?.qcad_pro?.installed ? "QCAD Pro not running" : "ezdxf mode"}
					</span>
					{status?.ezdxf_version && <span>ezdxf {status.ezdxf_version}</span>}
				</div>
			</div>
			<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-5 space-y-3" data-testid="kpi-server">
					<div className="flex items-center gap-2 text-amber-400">
						<Ruler size={18} /> ezdxf Engine
					</div>
					<p className="text-sm text-slate-300" data-testid="kpi-server-version">{status?.ezdxf_version || "..."}</p>
					<p className="text-sm text-slate-400" data-testid="kpi-qcad">
						{status?.qcad_pro?.running ? `QCAD Pro ${status.qcad_pro.version} (running)` : status?.qcad_pro?.installed ? "QCAD Pro installed (not running)" : "QCAD Pro: not found (PDF via ezdxf)"}
					</p>
				</div>
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-5 space-y-3" data-testid="kpi-files">
					<div className="flex items-center gap-2 text-emerald-400">
						<FileText size={18} /> Files
					</div>
					<p className="text-2xl font-bold text-white" data-testid="kpi-uploads">
						{files.uploads} <span className="text-sm font-normal text-slate-300">uploads</span>
					</p>
					<p className="text-2xl font-bold text-white" data-testid="kpi-outputs">
						{files.outputs} <span className="text-sm font-normal text-slate-300">outputs</span>
					</p>
				</div>
				<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-5 space-y-3">
					<div className="flex items-center gap-2 text-indigo-400">
						<Layers size={18} /> Quick Actions
					</div>
					<a href="/depot" className="block text-sm text-amber-400 hover:underline">
						Open CAD Depot
					</a>
					<a href="/viewer" className="block text-sm text-amber-400 hover:underline">
						View Floor Plan
					</a>
					<a href="/extrude" className="block text-sm text-amber-400 hover:underline">
						Extrude to 3D
					</a>
				</div>
			</div>
			<div className="grid grid-cols-2 md:grid-cols-5 gap-3">
				{[
					{
						href: "/depot",
						icon: Database,
						label: "Depot",
						desc: "CAD file depot",
					},
					{
						href: "/viewer",
						icon: Layers,
						label: "Viewer",
						desc: "DXF → SVG preview",
					},
					{
						href: "/extrude",
						icon: Box,
						label: "Extrude",
						desc: "Walls → 3D STL",
					},
					{
						href: "/analyse",
						icon: BarChart3,
						label: "Analyse",
						desc: "Rooms & areas",
					},
					{
						href: "/models",
						icon: FileText,
						label: "Models",
						desc: "Download outputs",
					},
				].map((item) => (
					<a
						key={item.href}
						href={item.href}
						className="bg-[#1e1e26] border border-white/10 rounded-2xl p-4 text-center hover:border-amber-500/20 transition-all"
					>
						<item.icon size={24} className="mx-auto mb-2 text-amber-400" />
						<p className="text-sm font-bold text-slate-300">{item.label}</p>
						<p className="text-sm text-slate-400">{item.desc}</p>
					</a>
				))}
			</div>
		</div>
	);
}
