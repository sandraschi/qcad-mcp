import {
	BookOpen,
	Box,
	Code2,
	Cpu,
	ExternalLink,
	GitCompare,
	HelpCircle,
	History,
	Layers,
	Network,
	Package,
	Ruler,
	Wrench,
} from "lucide-react";
import { useState } from "react";

const sections = [
	{ id: "intro", label: "QCAD", icon: BookOpen },
	{ id: "ezdxf", label: "ezdxf Engine", icon: Cpu },
	{ id: "history", label: "History", icon: History },
	{ id: "scripting", label: "Scripting", icon: Code2 },
	{ id: "comparison", label: "vs AutoCAD", icon: GitCompare },
	{ id: "tools", label: "MCP Tools", icon: Wrench },
	{ id: "pipeline", label: "Pipeline", icon: Box },
	{ id: "formats", label: "Formats", icon: Layers },
	{ id: "fleet", label: "Fleet", icon: Network },
	{ id: "links", label: "Links", icon: ExternalLink },
];

export default function HelpPage() {
	const [tab, setTab] = useState("intro");
	return (
		<div className="max-w-4xl space-y-6">
			<h1 className="text-2xl font-bold text-white flex items-center gap-3">
				<HelpCircle className="text-amber-400" /> Help &amp; Reference
			</h1>
			<div className="flex flex-wrap gap-1.5 p-1 bg-white/10 rounded-2xl">
				{sections.map((s) => (
					<button
						type="button"
						key={s.id}
						onClick={() => setTab(s.id)}
						className={`px-3.5 py-2 rounded-xl text-sm font-bold uppercase tracking-wider transition-all ${tab === s.id ? "bg-amber-600 text-white shadow-lg shadow-amber-600/20" : "text-slate-300 hover:text-slate-300"}`}
					>
						<s.icon size={13} className="inline mr-1.5" />
						{s.label}
					</button>
				))}
			</div>
			<div className="bg-[#1e1e26] border border-white/10 rounded-2xl p-6 text-sm text-slate-400 leading-relaxed space-y-4">
				{tab === "intro" && (
					<>
						<p>
							<strong className="text-slate-200">QCAD</strong> is a professional
							2D CAD application, Swiss-made by RibbonSoft since 1999. It works
							with DXF and DWG — the industry standard for 2D construction
							drawings, floor plans, and mechanical drafting.
						</p>
						<p>
							The <strong className="text-slate-200">Community Edition</strong>{" "}
							is free and open-source (GPLv2). The{" "}
							<strong className="text-slate-200">Professional Edition</strong>{" "}
							(~€50.40) adds DWG support and PDF export.
						</p>
						<p>
							This MCP server uses{" "}
							<strong className="text-slate-200">ezdxf</strong> (pure Python,
							MIT) as its core parsing engine — QCAD itself is optional. It
							reads DXF from R12 to R2023 without any binary dependencies.
						</p>
					</>
				)}

				{tab === "ezdxf" && (
					<>
						<p>
							<strong className="text-slate-200">ezdxf</strong> (by Manfred
							Moitzi) is a pure-Python library for reading and writing DXF
							files. No binary dependencies, MIT license, supports R12 through
							R2023.
						</p>
						<p>
							Entity types: LINE, ARC, CIRCLE, LWPOLYLINE, POLYLINE, SPLINE,
							HATCH, TEXT, MTEXT, DIMENSION, BLOCK, INSERT, and more.
						</p>
						<p>
							QCAD MCP uses ezdxf for: parsing, layer/block iteration, bounding
							box calculation, SVG rendering (via matplotlib), wall detection
							and STL extrusion (via shapely + numpy-stl), room area analysis,
							and DXF creation from scratch.
						</p>
						<p>
							<strong className="text-slate-200">Why not QCAD CLI?</strong>{" "}
							ezdxf is faster for batch processing (no GUI startup), gives full
							Python control over geometry, and avoids coupling to a specific
							QCAD version or platform.
						</p>
					</>
				)}

				{tab === "history" && (
					<>
						<div className="space-y-2">
							{[
								["1999", "RibbonSoft starts QCAD development in Switzerland"],
								["2004", "First stable release"],
								["2010", "Community Edition open-sourced under GPLv2"],
								["2015", "Professional Edition adds DWG support"],
								["2020", "Qt5 port with modern UI"],
								["2024", "Mature DXF/R12-R2023 support"],
							].map(([y, t]) => (
								<div key={y} className="flex gap-3">
									<span className="text-amber-400 font-bold text-sm shrink-0 w-12">
										{y}
									</span>
									<span>{t}</span>
								</div>
							))}
						</div>
						<p>
							Community: <strong className="text-slate-200">qcad.org</strong> —
							official site,{" "}
							<strong className="text-slate-200">ribbonsoft.com</strong> — QCAD
							Pro,{" "}
							<strong className="text-slate-200">ezdxf.readthedocs.io</strong> —
							ezdxf docs.
						</p>
					</>
				)}

				{tab === "scripting" && (
					<>
						<p>
							QCAD itself uses{" "}
							<strong className="text-slate-200">ECMAScript (QtScript)</strong>{" "}
							for scripting — similar to JavaScript, runs inside QCAD's Script
							Editor.
						</p>
						<p>
							However, the MCP server uses{" "}
							<strong className="text-slate-200">Python + ezdxf</strong> which
							is far more versatile:
						</p>
						<div className="bg-black/30 rounded-xl p-4 font-mono text-sm space-y-1 overflow-x-auto">
							<div>
								<span className="text-slate-300">import</span>{" "}
								<span className="text-emerald-400">ezdxf</span>
							</div>
							<div>
								doc = ezdxf.readfile(
								<span className="text-green-400">"floorplan.dxf"</span>)
							</div>
							<div className="text-slate-400"># List all layers</div>
							<div>
								<span className="text-slate-300">for</span> layer{" "}
								<span className="text-slate-300">in</span> doc.layers:
							</div>
							<div className="ml-4">print(layer.dxf.name, layer.dxf.color)</div>
							<div className="text-slate-400">
								# Get all LINE entities on "Walls" layer
							</div>
							<div>
								walls = doc.modelspace().query(
								<span className="text-green-400">'LINE[layer=="Walls"]'</span>)
							</div>
							<div>
								<span className="text-slate-300">for</span> wall{" "}
								<span className="text-slate-300">in</span> walls:
							</div>
							<div className="ml-4">
								length = wall.dxf.start.distance(wall.dxf.end)
							</div>
							<div className="ml-4">
								print(
								<span className="text-amber-400">
									f"Wall: {"{length:.1f}"} mm"
								</span>
								)
							</div>
						</div>
						<p>
							<strong className="text-slate-200">Core Python modules:</strong>{" "}
							<code className="text-amber-400">ezdxf</code> (DXF),{" "}
							<code className="text-amber-400">shapely</code> (geometry),{" "}
							<code className="text-amber-400">numpy-stl</code> (STL export),{" "}
							<code className="text-amber-400">matplotlib</code> (SVG/PNG).
						</p>
					</>
				)}

				{tab === "comparison" && (
					<>
						<div className="overflow-x-auto">
							<table className="w-full text-sm">
								<thead>
									<tr className="text-slate-200 border-b border-white/10">
										<th className="text-left py-2 pr-4">Aspect</th>
										<th className="text-left py-2 px-3 bg-amber-500/10 rounded-t-lg">
											QCAD
										</th>
										<th className="text-left py-2 px-3">AutoCAD</th>
									</tr>
								</thead>
								<tbody className="text-slate-400">
									{[
										["License", "GPLv2 / €50.40", "$2,000+/year"],
										["File Format", "DXF (native), DWG (Pro)", "DWG (native)"],
										["2D Drafting", "Full", "Full"],
										["3D", "No", "Yes"],
										["Scripting", "ECMAScript", "AutoLISP, .NET, VBA"],
										[
											"Python API",
											"ezdxf (full control)",
											"pyautocad (limited)",
										],
										["BIM", "No", "Yes (Revit)"],
										["Platform", "Win/Mac/Linux", "Win/Mac"],
										["Learning Curve", "Gentle", "Steep"],
									].map(([a, q, ac]) => (
										<tr
											key={a}
											className="border-b border-white/10 hover:bg-white/[0.02]"
										>
											<td className="py-2 pr-4 font-bold text-slate-300">
												{a}
											</td>
											<td className="py-2 px-3 bg-amber-500/5 text-amber-300">
												{q}
											</td>
											<td className="py-2 px-3">{ac}</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
						<p>
							<strong className="text-amber-400">QCAD wins</strong> when you
							need programmatic DXF processing, zero cost, or cross-platform
							support. <strong className="text-slate-300">AutoCAD wins</strong>{" "}
							for industry-standard DWG workflows, 3D, and enterprise PLM
							integration.
						</p>
					</>
				)}

				{tab === "tools" && (
					<>
						<p>
							<strong className="text-slate-200">7 MCP tools</strong> for 2D CAD
							operations.
						</p>
						<div className="space-y-2">
							{[
								{
									n: "plan_info",
									t: "READ",
									d: "DXF metadata: layers, entity counts, bounding box, blocks",
								},
								{
									n: "plan_to_svg",
									t: "MUTATE",
									d: "DXF → SVG preview with layer filtering and background colour",
								},
								{
									n: "plan_extrude",
									t: "MUTATE",
									d: "DXF walls → 3D STL mesh. The killer feature for game engines.",
								},
								{
									n: "plan_export",
									t: "MUTATE",
									d: "Export DXF to SVG, PNG, or PDF (QCAD Pro optional)",
								},
								{
									n: "plan_analyse",
									t: "READ",
									d: "Room detection, area calculation, door/window identification",
								},
								{
									n: "plan_create",
									t: "MUTATE",
									d: "Create DXF from primitives (line, rect, circle, text, polyline)",
								},
								{
									n: "plan_depot",
									t: "READ",
									d: "List files in the DXF depot with metadata",
								},
							].map((t) => (
								<div
									key={t.n}
									className="bg-white/10 rounded-xl p-3 flex items-start gap-3"
								>
									<span
										className={`text-sm font-bold uppercase px-2 py-0.5 rounded ${t.t === "READ" ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"}`}
									>
										{t.t}
									</span>
									<div>
										<code className="text-amber-400 font-bold">{t.n}()</code>
										<p className="text-sm text-slate-300 mt-0.5">{t.d}</p>
									</div>
								</div>
							))}
						</div>
					</>
				)}

				{tab === "pipeline" && (
					<>
						<h3 className="text-lg font-bold text-white mb-2">2D Drafting</h3>
						<div className="space-y-2 mb-6">
							{[
								["1. Upload", "Drop DXF/DWG on Depot or POST /api/v1/upload"],
								[
									"2. Inspect",
									"plan_info → layers, entities, bounding box, blocks",
								],
								[
									"3. Preview",
									"plan_to_svg → SVG in Viewer with per-layer toggle",
								],
								[
									"4. Analyse",
									"plan_analyse → room areas, door/window detection",
								],
								[
									"5. Modify",
									"plan_modify → delete, offset, rename, freeze layers",
								],
								[
									"6. Export",
									"plan_export → PDF (QCAD Pro) or SVG/PNG (ezdxf)",
								],
							].map(([step, desc]) => (
								<div
									key={step}
									className="flex gap-3 bg-white/10 rounded-lg p-2.5"
								>
									<span className="text-amber-400 font-bold text-sm shrink-0 w-20">
										{step}
									</span>
									<span className="text-sm text-slate-300">{desc}</span>
								</div>
							))}
						</div>

						<h3 className="text-lg font-bold text-white mb-2">
							AI CAD Automation
						</h3>
						<div className="space-y-2 mb-6">
							{[
								[
									"NL → DXF",
									"plan_agentic creates floor plans from natural language",
								],
								[
									"AutoLISP",
									"plan_transpile converts legacy LISP routines to ECMAScript",
								],
								[
									"ECMAScript",
									"plan_script executes arbitrary QCAD Pro scripts",
								],
								[
									"Script Library",
									"ScriptsPage: 12 curated scripts + GitHub Gist + QCAD examples",
								],
							].map(([step, desc]) => (
								<div
									key={step}
									className="flex gap-3 bg-white/10 rounded-lg p-2.5"
								>
									<span className="text-amber-400 font-bold text-sm shrink-0 w-20">
										{step}
									</span>
									<span className="text-sm text-slate-300">{desc}</span>
								</div>
							))}
						</div>

						<h3 className="text-lg font-bold text-white mb-2">
							3D &amp; BIM (Cross-Repo)
						</h3>
						<p className="text-sm text-slate-300 mb-3">
							Chain with <strong className="text-slate-200">freecad-mcp</strong>{" "}
							for full BIM pipeline:
						</p>
						<div className="space-y-2 mb-4">
							{[
								["Extrude", "plan_extrude → STL wall mesh (qcad-mcp)"],
								["Solid", "mesh_to_solid → FCStdB-Rep solid (freecad-mcp)"],
								["BIM Walls", "plan_wall_data + bim_create_wall per segment"],
								["BIM Slab", "bim_create_slab → floor structure"],
								["Windows", "bim_create_window → auto-cut openings in walls"],
								["Doors", "bim_create_door → auto-cut openings in walls"],
								["Roof", "bim_create_roof → sloped/flat roof"],
								["IFC", "bim_export_ifc → architect-standard BIM format"],
							].map(([step, desc]) => (
								<div
									key={step}
									className="flex gap-3 bg-white/10 rounded-lg p-2.5"
								>
									<span className="text-amber-400 font-bold text-sm shrink-0 w-20">
										{step}
									</span>
									<span className="text-sm text-slate-300">{desc}</span>
								</div>
							))}
						</div>
						<p className="text-sm text-slate-300">
							The STL can also be imported directly into{" "}
							<strong className="text-slate-200">Resonite</strong>,{" "}
							<strong className="text-slate-200">Unity3D</strong>,{" "}
							<strong className="text-slate-200">Blender</strong>, or sliced via{" "}
							<code className="text-amber-400">slice_stl</code> for 3D printing.
							See{" "}
							<code className="text-amber-400">docs/freecad-pipeline.md</code>{" "}
							for full guide.
						</p>
					</>
				)}

				{tab === "formats" &&
					[
						[
							"DXF (.dxf)",
							"Drawing eXchange Format — industry standard 2D CAD. ASCII or binary. R12 to R2023.",
						],
						[
							"DWG (.dwg)",
							"Native AutoCAD format (proprietary). QCAD Pro adds full support.",
						],
						[
							"SVG (.svg)",
							"Web-standard vector graphics. Generated by plan_to_svg / plan_export.",
						],
						[
							"STL (.stl)",
							"Triangle mesh for 3D printing and game engines. Generated by plan_extrude.",
						],
						[
							"PDF (.pdf)",
							"Portable document format for printing. QCAD Pro gives best quality.",
						],
						[
							"PNG (.png)",
							"Raster image export via matplotlib backend (configurable DPI).",
						],
					].map(([fmt, desc]) => (
						<p key={fmt}>
							<strong className="text-slate-200">{fmt}</strong> — {desc}
						</p>
					))}

				{tab === "fleet" && (
					<>
						<p className="text-sm text-slate-300 mb-3">
							qcad-mcp connects to the MCP fleet via shared formats (STL, IFC,
							SVG) and direct MCP tool chaining:
						</p>
						<div className="space-y-3">
							{[
								[
									"freecad-mcp",
									"10944",
									"STL → solid → BIM → IFC: mesh_to_solid, bim_create_*",
									"MeshPart",
								],
								[
									"resonite-mcp",
									"10979",
									"Import STL as XR world: static or interactive",
									"STL",
								],
								[
									"unity3d-mcp",
									"10831",
									"Import STL into Unity game engine scenes",
									"STL",
								],
								[
									"multi-backup-mcp",
									"10799",
									"Backup STL/FCStd/IFC outputs to cloud",
									"any",
								],
							].map(([repo, port, desc, fmt]) => (
								<div key={repo} className="bg-white/10 rounded-xl p-3">
									<div className="flex items-center gap-2 mb-1">
										<code className="text-amber-400 font-bold text-sm">
											{repo}
										</code>
										<span className="text-xs text-slate-500">:{port}</span>
										<span className="text-xs px-2 py-0.5 rounded bg-white/10 text-slate-400">
											{fmt}
										</span>
									</div>
									<p className="text-sm text-slate-300">{desc}</p>
								</div>
							))}
						</div>
						<p className="text-sm text-slate-300 mt-3">
							See{" "}
							<code className="text-amber-400">docs/freecad-pipeline.md</code>{" "}
							for the full cross-repo architecture and step-by-step chain from
							NL building description to IFC export.
						</p>
					</>
				)}

				{tab === "links" && (
					<div className="space-y-2">
						{[
							[
								"qcad.org",
								"Official QCAD website (download + docs)",
								"https://www.qcad.org",
							],
							[
								"ribbonsoft.com",
								"QCAD Pro purchase (€50.40)",
								"https://www.ribbonsoft.com",
							],
							[
								"ezdxf.readthedocs.io",
								"ezdxf Python library documentation",
								"https://ezdxf.readthedocs.io",
							],
							[
								"github.com/mozman/ezdxf",
								"ezdxf source code (MIT)",
								"https://github.com/mozman/ezdxf",
							],
							[
								"FreeCAD DXF reference",
								"DXF format guide on FreeCAD wiki",
								"https://wiki.freecad.org/DXF",
							],
							[
								"Resonite",
								"Social VR platform (STL import)",
								"https://resonite.com",
							],
						].map(([label, desc, url]) => (
							<a
								key={url}
								href={url}
								target="_blank"
								rel="noopener noreferrer"
								className="flex items-center justify-between p-3 rounded-xl bg-white/10 hover:bg-white/10 transition-all group"
							>
								<div>
									<span className="text-amber-400 font-bold text-sm group-hover:text-amber-300">
										{label}
									</span>
									<p className="text-sm text-slate-300">{desc}</p>
								</div>
								<ExternalLink
									size={14}
									className="text-slate-400 group-hover:text-slate-400"
								/>
							</a>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
