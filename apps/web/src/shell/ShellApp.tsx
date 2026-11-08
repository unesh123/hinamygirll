import { lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import App from "../App";
import { ChatHost } from "./ChatHost";
import { ShellLayout } from "./ShellLayout";
import { MODE_PATHS, getShellState } from "./store";

const GoalsPage = lazy(() => import("./pages/GoalsPage"));
const AutopilotPage = lazy(() => import("./pages/AutopilotPage"));
const SecurityPage = lazy(() => import("./pages/SecurityPage"));
const IntegrationsPage = lazy(() => import("./pages/IntegrationsPage"));
const MemoryPage = lazy(() => import("./pages/MemoryPage"));
const ProductivityPage = lazy(() => import("./pages/ProductivityPage"));
const NewsPage = lazy(() => import("./pages/NewsPage"));
const OrganisationPage = lazy(() => import("./pages/OrganisationPage"));

function ModeHome() {
  return <Navigate to={MODE_PATHS[getShellState().mode]} replace />;
}

/** Route table, router-agnostic so tests can wrap it in a MemoryRouter. */
export function ShellRoutes() {
  return (
    <Routes>
      <Route path="/dev/voice-lab" element={<App />} />
      <Route element={<ShellLayout />}>
        <Route path="/" element={<ModeHome />} />
        <Route element={<ChatHost />}>
          <Route path="/workspace" element={null} />
          <Route path="/companion" element={null} />
        </Route>
        <Route path="/goals" element={<GoalsPage />} />
        <Route path="/autopilot" element={<AutopilotPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
        <Route path="/memory" element={<MemoryPage />} />
        <Route path="/productivity" element={<ProductivityPage />} />
        <Route path="/news" element={<NewsPage />} />
        <Route path="/organisation" element={<OrganisationPage />} />
        <Route path="*" element={<ModeHome />} />
      </Route>
    </Routes>
  );
}

export default function ShellApp() {
  return (
    <BrowserRouter>
      <ShellRoutes />
    </BrowserRouter>
  );
}
