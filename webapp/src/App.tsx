import { Route, Routes, Navigate } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import Dashboard from "./pages/Dashboard";
import DepotPage from "./pages/DepotPage";
import ViewerPage from "./pages/ViewerPage";
import ExtrudePage from "./pages/ExtrudePage";
import AnalysePage from "./pages/AnalysePage";
import BlocksPage from "./pages/BlocksPage";
import ModelsPage from "./pages/ModelsPage";
import LogsPage from "./pages/LogsPage";
import SettingsPage from "./pages/SettingsPage";
import HelpPage from "./pages/HelpPage";

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/depot" element={<DepotPage />} />
        <Route path="/viewer" element={<ViewerPage />} />
        <Route path="/extrude" element={<ExtrudePage />} />
        <Route path="/analyse" element={<AnalysePage />} />
        <Route path="/blocks" element={<BlocksPage />} />
        <Route path="/models" element={<ModelsPage />} />
        <Route path="/logs" element={<LogsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/help" element={<HelpPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}
