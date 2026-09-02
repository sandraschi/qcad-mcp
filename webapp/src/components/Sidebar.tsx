import { motion } from "framer-motion";
import {
	BarChart3,
	Bot,
	Box,
	ChevronLeft,
	ChevronRight,
	Code2,
	Database,
	FileText,
	GitBranch,
	Grid3X3,
	HelpCircle,
	Layers,
	LayoutDashboard,
	Logs,
	Play,
	Ruler,
	Settings,
	SlidersHorizontal,
	Sparkles,
	Terminal,
} from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
	{ path: "/", label: "Dashboard", icon: LayoutDashboard },
	{ path: "/demo", label: "Demo", icon: Sparkles },
	{ path: "/agentic", label: "AI Agent", icon: Bot },
	{ path: "/depot", label: "Depot", icon: Database },
	{ path: "/viewer", label: "Viewer", icon: Layers },
	{ path: "/extrude", label: "Extrude", icon: Box },
	{ path: "/analyse", label: "Analyse", icon: BarChart3 },
	{ path: "/layers", label: "Layers", icon: SlidersHorizontal },
	{ path: "/blocks", label: "Blocks", icon: Grid3X3 },
	{ path: "/scripts", label: "Scripts", icon: Code2 },
	{ path: "/batch", label: "Batch", icon: Play },
	{ path: "/pipeline", label: "Pipeline", icon: GitBranch },
	{ path: "/models", label: "Models", icon: FileText },
	{ path: "/logs", label: "Logs", icon: Logs },
	{ path: "/settings", label: "Settings", icon: Settings },
	{ path: "/playground", label: "Playground", icon: Terminal },
	{ path: "/help", label: "Help", icon: HelpCircle },
];

export default function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
	return (
		<motion.aside
			animate={{ width: collapsed ? 72 : 240 }}
			className="flex flex-col bg-[#1e1e26] border-r border-white/10 h-full shrink-0 overflow-hidden relative"
		>
			<div className="h-14 flex items-center gap-3 px-4 border-b border-white/10 overflow-hidden">
				<Ruler className="text-amber-400 shrink-0" size={22} />
				<motion.span
					animate={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : "auto" }}
					className="text-sm font-bold text-white whitespace-nowrap overflow-hidden"
				>
					QCAD MCP
				</motion.span>
				<button
					type="button"
					onClick={onToggle}
					className="ml-auto p-1.5 rounded-lg hover:bg-white/10 text-slate-400 hover:text-white transition-all shrink-0"
					title={collapsed ? "Expand" : "Collapse"}
				>
					{collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
				</button>
			</div>
			<nav className="flex-1 p-3 space-y-1 overflow-y-auto">
				{navItems.map((item) => (
					<NavLink
						key={item.path}
						to={item.path}
						end={item.path === "/"}
						className={({ isActive }) =>
							`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
								isActive
									? "bg-amber-600 text-white shadow-lg shadow-amber-600/20"
									: "text-slate-400 hover:text-slate-200 hover:bg-white/[0.12]"
							}`
						}
					>
						<item.icon size={18} className="shrink-0" />
						<motion.span
							animate={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : "auto" }}
							className="whitespace-nowrap overflow-hidden"
						>
							{item.label}
						</motion.span>
					</NavLink>
				))}
			</nav>
		</motion.aside>
	);
}
