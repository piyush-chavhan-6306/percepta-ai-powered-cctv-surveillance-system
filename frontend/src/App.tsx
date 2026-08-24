import React, { useState } from 'react';
import { SurveillanceProvider, useSurveillance } from './store/surveillanceContext';
import { Header } from './components/Header';
import { Navigation } from './components/Navigation';
import { PresentationMode } from './components/PresentationMode';
import { DashboardView } from './views/DashboardView';
import { SurveillanceView } from './views/SurveillanceView';
import { IncidentsView } from './views/IncidentsView';
import { ZonesView } from './views/ZonesView';
import { ThreatView } from './views/ThreatView';
import { ForensicsView } from './views/ForensicsView';
import { SensorsSystemView } from './views/SensorsSystemView';
import { IntelligenceView } from './views/IntelligenceView';
import { LandingView } from './views/LandingView';
import { SimulationDashboard } from './views/SimulationDashboard';
import { ShieldCheck, Activity, Database, Zap } from 'lucide-react';

const MainLayout: React.FC = () => {
  const { activeView } = useSurveillance();
  const [isPresentationMode, setIsPresentationMode] = useState<boolean>(false);

  const renderActiveView = () => {
    switch (activeView) {
      case 'simulation':
        return <SimulationDashboard />;
      case 'landing':
        return <LandingView />;
      case 'dashboard':
        return <DashboardView />;
      case 'surveillance':
        return <SurveillanceView />;
      case 'operations':
      case 'incidents':
        return <IncidentsView />;
      case 'zones':
        return <ZonesView />;
      case 'threat':
        return <ThreatView />;
      case 'forensics':
        return <ForensicsView />;
      case 'sensors':
        return <SensorsSystemView />;
      case 'intelligence':
        return <IntelligenceView />;
      default:
        return <DashboardView />;
    }
  };

  if (isPresentationMode) {
    return <PresentationMode onExit={() => setIsPresentationMode(false)} />;
  }

  return (
    <div className="min-h-screen bg-[#05070a] text-gray-200 flex flex-col justify-between tactical-grid-bg font-sans">
      <div>
        <Header onTogglePresentation={() => setIsPresentationMode(true)} />
        <Navigation />
        {/* simulation and landing render full-bleed */}
        {(activeView === 'simulation' || activeView === 'landing')
          ? <main style={{ padding: 0 }}>{renderActiveView()}</main>
          : <main className="p-4 max-w-[1920px] mx-auto w-full">{renderActiveView()}</main>
        }
      </div>

      {/* Tactical Defense Footer */}
      <footer className="bg-[#070a10] border-t border-white/10 px-5 py-2.5 flex items-center justify-between text-[11px] font-mono-tech text-gray-400 flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#00e676]" />
          <span className="text-gray-300 font-bold">BORDER INTELLIGENCE COMMAND POST (C2)</span>
          <span className="text-gray-500">•</span>
          <span>PS SIH26187</span>
        </div>

        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <Database className="w-3.5 h-3.5 text-[#00e5ff]" />
            <span>PERSISTENCE: <strong className="text-gray-200">SQLITE WAL (PERSIST-BEFORE-PUBLISH)</strong></span>
          </span>
          <span className="flex items-center gap-1">
            <Zap className="w-3.5 h-3.5 text-[#00e676]" />
            <span>AI ENGINE: <strong className="text-gray-200">YOLOV8N + BYTETRACK KALMAN</strong></span>
          </span>
          <span className="flex items-center gap-1">
            <Activity className="w-3.5 h-3.5 text-[#ffab00]" />
            <span>BACKEND: <strong className="text-[#00e676]">FROZEN (130/130 VERIFIED)</strong></span>
          </span>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <SurveillanceProvider>
      <MainLayout />
    </SurveillanceProvider>
  );
};

export default App;
