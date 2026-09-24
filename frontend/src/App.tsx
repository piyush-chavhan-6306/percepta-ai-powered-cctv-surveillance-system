import React, { useState } from "react";
import { Routes, Route, Navigate, useSearchParams } from "react-router";
import { SurveillanceProvider, useSurveillance } from "./store/surveillanceContext";
import { Header } from "./components/Header";
import { Navigation } from "./components/Navigation";
import { AddCameraModal } from "./components/AddCameraModal";
import { DashboardView } from "./views/DashboardView";
import { IncidentsView } from "./views/IncidentsView";
import { ZonesView } from "./views/ZonesView";
import { ForensicsView } from "./views/ForensicsView";
import { IntelligenceView } from "./views/IntelligenceView";
import { TacticalAnalyticsView } from "./views/TacticalAnalyticsView";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";

/* ─── Command Center Layout (Exact Reference Composition) ─────────────────── */
const CommandCenterLayout: React.FC = () => {
  const { activeView, registerCameraLocally } = useSurveillance();
  const [searchParams] = useSearchParams();
  const [isAddCameraOpen, setIsAddCameraOpen] = useState<boolean>(
    searchParams.get("modal") === "add_camera" || searchParams.get("add") === "1"
  );

  const renderActiveView = () => {
    switch (activeView) {
      case "dashboard":
      case "cameras":
      case "telemetry":
        return <DashboardView onRegisterFeed={() => setIsAddCameraOpen(true)} />;
      case "analytics":
        return <TacticalAnalyticsView />;
      case "incidents":
        return <IncidentsView />;
      case "entities":
      case "forensics":
        return <ForensicsView />;
      case "zones":
        return <ZonesView />;
      case "intelligence":
        return <IntelligenceView />;
      default:
        return <DashboardView onRegisterFeed={() => setIsAddCameraOpen(true)} />;
    }
  };

  return (
    <div className="h-screen w-screen max-h-screen tactical-space-bg text-[#cbd5e1] flex flex-col font-sans select-none antialiased text-xs bg-tactical-void overflow-hidden">
      {/* ── Top Command Header ── */}
      <Header onRegisterFeed={() => setIsAddCameraOpen(true)} />

      {/* ── Tactical Navigation Bar (C2 vs Intelligence & Analytics) ── */}
      <Navigation />

      {/* ── Main Operational Workspace ── */}
      <div className="flex-1 overflow-hidden w-full flex flex-col min-h-0">
        {renderActiveView()}
      </div>

      {/* ── Register Feed Modal ── */}
      <AddCameraModal
        isOpen={isAddCameraOpen}
        onClose={() => setIsAddCameraOpen(false)}
        onCameraAdded={(cam, previewUrl) => {
          registerCameraLocally(cam, previewUrl);
          setIsAddCameraOpen(false);
        }}
      />
    </div>
  );
};

/* ─── App Root ────────────────────────────────────────────────────────────── */
export default function App() {
  return (
    <Routes>
      {/* Public Landing & Authentication */}
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<Auth />} />

      {/* Operational Command Center */}
      <Route
        path="/dashboard/*"
        element={
          <SurveillanceProvider>
            <CommandCenterLayout />
          </SurveillanceProvider>
        }
      />

      {/* Fallback Redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
