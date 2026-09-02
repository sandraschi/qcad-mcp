import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import FloatingChat from "./components/FloatingChat";
import AgenticPage from "./pages/AgenticPage";
import AnalysePage from "./pages/AnalysePage";
import BatchPage from "./pages/BatchPage";
import BlocksPage from "./pages/BlocksPage";
import Dashboard from "./pages/Dashboard";
import DemoPage from "./pages/DemoPage";
import DepotPage from "./pages/DepotPage";
import ExtrudePage from "./pages/ExtrudePage";
import HelpPage from "./pages/HelpPage";
import LayersPage from "./pages/LayersPage";
import LogsPage from "./pages/LogsPage";
import ModelsPage from "./pages/ModelsPage";
import PipelinePage from "./pages/PipelinePage";
import PlaygroundPage from "./pages/PlaygroundPage";
import ScriptsPage from "./pages/ScriptsPage";
import SettingsPage from "./pages/SettingsPage";
import ViewerPage from "./pages/ViewerPage";

export default function App() {
	return (
		<AppLayout>
			<Routes>
				<Route path="/" element={<Dashboard />} />
				<Route path="/demo" element={<DemoPage />} />
				<Route path="/agentic" element={<AgenticPage />} />
				<Route path="/depot" element={<DepotPage />} />
				<Route path="/viewer" element={<ViewerPage />} />
				<Route path="/extrude" element={<ExtrudePage />} />
				<Route path="/analyse" element={<AnalysePage />} />
				<Route path="/blocks" element={<BlocksPage />} />
				<Route path="/scripts" element={<ScriptsPage />} />
				<Route path="/layers" element={<LayersPage />} />
				<Route path="/batch" element={<BatchPage />} />
				<Route path="/models" element={<ModelsPage />} />
				<Route path="/pipeline" element={<PipelinePage />} />
				<Route path="/playground" element={<PlaygroundPage />} />
				<Route path="/logs" element={<LogsPage />} />
				<Route path="/settings" element={<SettingsPage />} />
				<Route path="/help" element={<HelpPage />} />
				<Route path="*" element={<Navigate to="/" replace />} />
			</Routes>
			<FloatingChat />
		</AppLayout>
	);
}
