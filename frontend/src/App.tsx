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

import { getCurrentSession } from "./lib/auth";
import { Loader2 } from "lucide-react";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  React.useEffect(() => {
    getCurrentSession().then((session) => {
      setIsAuthenticated(Boolean(session && session.access_token));
    });
  }, []);

  if (isAuthenticated === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-[#05070a] text-gray-400 font-mono text-xs">
        <Loader2 className="w-5 h-5 animate-spin mr-2 text-[#00e5ff]" />
        VERIFYING OPERATOR CLEARANCE...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth?redirect=/dashboard" replace />;
  }

  return <>{children}</>;
}

/* ─── App Root ────────────────────────────────────────────────────────────── */
export default function App() {
  return (
    <Routes>
      {/* Public Landing & Authentication */}
      <Route path="/" element={<Landing />} />
      <Route path="/auth" element={<Auth />} />

      {/* Operational Command Center (Protected by Operator Clearance Guard) */}
      <Route
        path="/dashboard/*"
        element={
          <ProtectedRoute>
            <SurveillanceProvider>
              <CommandCenterLayout />
            </SurveillanceProvider>
          </ProtectedRoute>
        }
      />

      {/* Fallback Redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
