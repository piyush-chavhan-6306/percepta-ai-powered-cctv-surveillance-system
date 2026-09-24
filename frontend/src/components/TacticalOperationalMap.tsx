import React, { useState, useRef, useEffect } from "react";
import {
  Compass,
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Radio,
  Eye,
  Crosshair,
  ShieldAlert,
} from "lucide-react";

interface TacticalOperationalMapProps {
  selectedCameraId?: string;
  onSelectCamera?: (camId: string) => void;
  onSelectIncident?: (incidentId: string) => void;
}

export const TacticalOperationalMap: React.FC<TacticalOperationalMapProps> = ({
  selectedCameraId = "CAM-04",
  onSelectCamera,
  onSelectIncident,
}) => {
  const [viewMode, setViewMode] = useState<"2D" | "3D">("3D");
  const [mapType, setMapType] = useState<"SAT" | "TOPO">("TOPO");
  const [zoom, setZoom] = useState<number>(1);
  const [activeCam, setActiveCam] = useState<string>(selectedCameraId);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Cameras on the tactical operational field
  const cameras = [
    { id: "CAM-01", name: "Sector 01 Access", x: 280, y: 520, angle: -0.6, fov: 0.8, online: true },
    { id: "CAM-02", name: "Corridor Bravo", x: 490, y: 440, angle: -1.2, fov: 0.9, online: true },
    { id: "CAM-03", name: "North Ridge", x: 420, y: 160, angle: 1.1, fov: 0.75, online: true },
    { id: "CAM-04", name: "Perimeter Sector 4", x: 740, y: 310, angle: 2.3, fov: 0.85, online: true, hasIncident: true },
  ];

  // Entity trajectory trail: CAM-01 -> CAM-02 -> CAM-04
  const entityTrack = [
    { x: 285, y: 515, time: "14:31:02", cam: "CAM-01" },
    { x: 380, y: 480, time: "14:31:25", cam: "TRANSIT" },
    { x: 495, y: 435, time: "14:31:46", cam: "CAM-02" },
    { x: 620, y: 370, time: "14:32:04", cam: "TRANSIT" },
    { x: 735, y: 315, time: "14:32:18", cam: "CAM-04" },
  ];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let sweepAngle = 0;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;

      // 1. Clear background to defense obsidian
      ctx.fillStyle = mapType === "TOPO" ? "#06090d" : "#040608";
      ctx.fillRect(0, 0, w, h);

      // Save context for transform (zoom, pan, 3D tilt)
      ctx.save();
      ctx.translate(w / 2, h / 2);
      ctx.scale(zoom, zoom);
      if (viewMode === "3D") {
        // Perspective squashing for tactical isometric HUD effect
        ctx.scale(1, 0.78);
        ctx.rotate(-0.04);
      }
      ctx.translate(-w / 2, -h / 2);

      // 2. Coordinate Tactical Grid
      ctx.strokeStyle = "rgba(158, 231, 223, 0.04)";
      ctx.lineWidth = 1;
      const gridSize = 48;
      for (let x = 0; x < w; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // 3. Topographic Elevation Contour Lines (Clean, dark, military)
      if (mapType === "TOPO") {
        ctx.strokeStyle = "rgba(158, 231, 223, 0.065)";
        ctx.lineWidth = 1;
        [160, 260, 360, 460].forEach((r, idx) => {
          ctx.beginPath();
          ctx.ellipse(w * 0.48, h * 0.45, r * 1.4, r * 0.95, 0.25, 0, Math.PI * 2);
          ctx.stroke();
          // elevation labels
          if (idx % 2 === 0) {
            ctx.fillStyle = "rgba(158, 231, 223, 0.25)";
            ctx.font = "8px monospace";
            ctx.fillText(`ELV +${320 + idx * 40}M`, w * 0.48 + r * 1.1, h * 0.45);
          }
        });
      }

      // 4. Roads / Patrol Logistics Vectors
      ctx.strokeStyle = "rgba(214, 193, 155, 0.15)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(80, 600);
      ctx.quadraticCurveTo(340, 540, 510, 450);
      ctx.quadraticCurveTo(680, 370, 920, 280);
      ctx.stroke();

      // Patrol vector label
      ctx.fillStyle = "rgba(214, 193, 155, 0.4)";
      ctx.font = "9px monospace";
      ctx.fillText("PATROL CORRIDOR CHARLIE", 200, 565);

      // 5. Perimeter Fence Line (Dashed high-contrast cyan/gold)
      ctx.save();
      ctx.strokeStyle = "rgba(158, 231, 223, 0.45)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([8, 5]);
      ctx.beginPath();
      ctx.moveTo(140, 200);
      ctx.lineTo(440, 130);
      ctx.lineTo(820, 230);
      ctx.lineTo(960, 480);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle = "rgba(158, 231, 223, 0.6)";
      ctx.font = "8.5px monospace";
      ctx.fillText("── PRIMARY DEMARCATION PERIMETER ──", 450, 120);

      // 6. Restricted Zone Boundary Polygon
      ctx.save();
      ctx.fillStyle = "rgba(248, 113, 113, 0.05)";
      ctx.strokeStyle = "rgba(248, 113, 113, 0.45)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(660, 240);
      ctx.lineTo(860, 200);
      ctx.lineTo(900, 390);
      ctx.lineTo(700, 430);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // Hatching inside restricted zone
      ctx.strokeStyle = "rgba(248, 113, 113, 0.08)";
      ctx.lineWidth = 1;
      for (let i = 0; i < 180; i += 20) {
        ctx.beginPath();
        ctx.moveTo(670 + i, 240);
        ctx.lineTo(720 + i, 420);
        ctx.stroke();
      }
      ctx.restore();

      // 7. Structures & Outposts
      const outposts = [
        { name: "HQ C2 RELAY", x: 190, y: 470, w: 28, h: 20 },
        { name: "OUTPOST BRAVO", x: 480, y: 390, w: 24, h: 18 },
        { name: "RADAR TOWER 04", x: 720, y: 260, w: 20, h: 20 },
      ];
      outposts.forEach((op) => {
        ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
        ctx.fillStyle = "#0c131a";
        ctx.lineWidth = 1;
        ctx.fillRect(op.x - op.w / 2, op.y - op.h / 2, op.w, op.h);
        ctx.strokeRect(op.x - op.w / 2, op.y - op.h / 2, op.w, op.h);
        ctx.fillStyle = "rgba(132, 144, 146, 0.8)";
        ctx.font = "8px monospace";
        ctx.fillText(op.name, op.x - op.w / 2, op.y - op.h / 2 - 4);
      });

      // 8. Tracked Entity Trajectory Trail (Dotted Cyan/Amber Flow)
      ctx.save();
      ctx.strokeStyle = "rgba(214, 193, 155, 0.7)";
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      entityTrack.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt.x, pt.y);
        else ctx.lineTo(pt.x, pt.y);
      });
      ctx.stroke();
      ctx.restore();

      // 9. Camera Coverage Cones & Radar Nodes
      sweepAngle += 0.02;
      cameras.forEach((cam) => {
        const isSelected = cam.id === activeCam;

        // Draw Field-Of-View (FOV) Cone
        ctx.save();
        ctx.translate(cam.x, cam.y);
        const fovRadius = 140;
        const startAng = cam.angle - cam.fov / 2;
        const endAng = cam.angle + cam.fov / 2;

        const coneGrad = ctx.createRadialGradient(0, 0, 10, 0, 0, fovRadius);
        coneGrad.addColorStop(0, isSelected ? "rgba(158, 231, 223, 0.25)" : "rgba(158, 231, 223, 0.12)");
        coneGrad.addColorStop(1, "rgba(158, 231, 223, 0.0)");

        ctx.fillStyle = coneGrad;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.arc(0, 0, fovRadius, startAng, endAng);
        ctx.closePath();
        ctx.fill();

        // Subtle arc sweep line
        ctx.strokeStyle = isSelected ? "rgba(158, 231, 223, 0.7)" : "rgba(158, 231, 223, 0.25)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(0, 0, fovRadius, startAng, endAng);
        ctx.stroke();

        // Active camera radar sweep arm
        if (isSelected) {
          const currentSweep = startAng + ((Math.sin(sweepAngle) + 1) / 2) * cam.fov;
          ctx.strokeStyle = "rgba(158, 231, 223, 0.85)";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(0, 0);
          ctx.lineTo(Math.cos(currentSweep) * fovRadius, Math.sin(currentSweep) * fovRadius);
          ctx.stroke();
        }

        ctx.restore();

        // Camera Node Icon & Label
        ctx.fillStyle = isSelected ? "#9ee7df" : "#00e676";
        ctx.beginPath();
        ctx.arc(cam.x, cam.y, isSelected ? 5.5 : 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cam.x, cam.y, isSelected ? 9 : 7, 0, Math.PI * 2);
        ctx.stroke();

        // Label
        ctx.fillStyle = isSelected ? "#ffffff" : "rgba(232, 235, 230, 0.85)";
        ctx.font = isSelected ? "bold 10px monospace" : "9px monospace";
        ctx.fillText(cam.id, cam.x + 12, cam.y + 3);
      });

      // 10. Active Incident Beacon (Pulsing Red Rings at CAM-04)
      const incidentCam = cameras.find((c) => c.hasIncident) || cameras[3];
      const pulseSize = 16 + (Math.sin(sweepAngle * 2) + 1) * 14;

      ctx.strokeStyle = "rgba(248, 113, 113, 0.85)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(incidentCam.x, incidentCam.y, pulseSize, 0, Math.PI * 2);
      ctx.stroke();

      ctx.strokeStyle = "rgba(248, 113, 113, 0.4)";
      ctx.beginPath();
      ctx.arc(incidentCam.x, incidentCam.y, pulseSize * 1.5, 0, Math.PI * 2);
      ctx.stroke();

      // Incident Callout Badge matching reference
      ctx.save();
      const tagX = incidentCam.x + 28;
      const tagY = incidentCam.y - 18;
      ctx.fillStyle = "rgba(20, 6, 8, 0.92)";
      ctx.strokeStyle = "rgba(248, 113, 113, 0.75)";
      ctx.lineWidth = 1;
      ctx.strokeRect(tagX, tagY, 136, 32);
      ctx.fillRect(tagX, tagY, 136, 32);

      ctx.fillStyle = "#f87171";
      ctx.font = "bold 8.5px monospace";
      ctx.fillText("INCIDENT", tagX + 8, tagY + 13);
      ctx.fillStyle = "#ffffff";
      ctx.font = "8px monospace";
      ctx.fillText("RESTRICTED-ZONE", tagX + 8, tagY + 25);
      ctx.restore();

      // 11. Target Marker (PERSON-042)
      const currentPos = entityTrack[entityTrack.length - 1];
      ctx.fillStyle = "#f87171";
      ctx.beginPath();
      ctx.arc(currentPos.x, currentPos.y, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
    };
  }, [viewMode, mapType, zoom, activeCam]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const clickX = (e.clientX - rect.left) * scaleX;
    const clickY = (e.clientY - rect.top) * scaleY;

    // Check proximity to cameras
    for (const cam of cameras) {
      const dist = Math.hypot(clickX - cam.x, clickY - cam.y);
      if (dist < 32) {
        setActiveCam(cam.id);
        onSelectCamera?.(cam.id);
        if (cam.hasIncident) {
          onSelectIncident?.("INC-RESTRICTED-ZONE");
        }
        return;
      }
    }
  };

  return (
    <div className="relative w-full h-full min-h-[580px] bg-[#07090c] rounded-none overflow-hidden border border-[#171e27] select-none flex flex-col justify-between">
      {/* ── Canvas Layer ── */}
      <canvas
        ref={canvasRef}
        width={1024}
        height={720}
        onClick={handleCanvasClick}
        className="absolute inset-0 w-full h-full object-cover cursor-crosshair"
      />

      {/* ── Top-Left Tactical HUD Overlay (Stitch Precision) ── */}
      <div className="relative z-10 p-5 flex flex-col gap-1 pointer-events-none">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-none bg-[#38e8cb] animate-pulse" />
          <span className="font-mono text-[10px] tracking-[0.24em] text-[#38e8cb] uppercase font-semibold">
            TACTICAL OPERATIONAL MAP // SECTOR 4
          </span>
        </div>
        <div className="font-display text-xl font-normal text-white tracking-[0.06em] uppercase">
          NORTH PERIMETER ZONE
        </div>
        <div className="font-mono text-[10px] text-[#8492a6] tracking-widest">
          37.0902° N &nbsp; -95.7129° W
        </div>
      </div>

      {/* ── Top-Right Map Controls ── */}
      <div className="relative z-10 p-3 self-end flex items-center gap-1.5 bg-[#0c1017]/90 backdrop-blur-md rounded-none border border-[#1b232f] m-3">
        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(1.6, z + 0.15))}
          className="p-1.5 text-[#8492a6] hover:text-[#38e8cb] transition-colors cursor-pointer"
          title="Zoom In"
        >
          <ZoomIn size={14} />
        </button>
        <button
          type="button"
          onClick={() => setZoom((z) => Math.max(0.75, z - 0.15))}
          className="p-1.5 text-[#8492a6] hover:text-[#38e8cb] transition-colors cursor-pointer"
          title="Zoom Out"
        >
          <ZoomOut size={14} />
        </button>
        <div className="h-3 w-px bg-[#171e27] mx-1" />
        <button
          type="button"
          onClick={() => setZoom(1)}
          className="p-1.5 text-[#8492a6] hover:text-[#38e8cb] transition-colors cursor-pointer"
          title="Reset View"
        >
          <Compass size={14} />
        </button>
      </div>

      {/* ── Bottom Bar: Toggles & Operational Telemetry ── */}
      <div className="relative z-10 p-4 flex flex-wrap items-center justify-between gap-4 bg-gradient-to-t from-[#07090c] via-[#07090c]/90 to-transparent">
        {/* View Mode Buttons (2D / 3D / SAT / TOPO per Stitch DESIGN.md) */}
        <div className="flex items-center gap-1 p-1 bg-[#0c1017]/95 rounded-none border border-[#1b232f] font-mono text-[10px] font-semibold">
          <button
            type="button"
            onClick={() => setViewMode("2D")}
            className={`px-3 py-1 rounded-none transition-all cursor-pointer ${
              viewMode === "2D"
                ? "bg-[#38e8cb]/15 text-[#38e8cb] border border-[#38e8cb]/50"
                : "text-[#8492a6] hover:text-white"
            }`}
          >
            2D
          </button>
          <button
            type="button"
            onClick={() => setViewMode("3D")}
            className={`px-3 py-1 rounded-none transition-all cursor-pointer ${
              viewMode === "3D"
                ? "bg-[#38e8cb]/15 text-[#38e8cb] border border-[#38e8cb]/50"
                : "text-[#8492a6] hover:text-white"
            }`}
          >
            3D
          </button>
          <div className="h-3 w-px bg-[#171e27] mx-0.5" />
          <button
            type="button"
            onClick={() => setMapType("SAT")}
            className={`px-3 py-1 rounded-none transition-all cursor-pointer ${
              mapType === "SAT"
                ? "bg-[#dcc495]/20 text-[#dcc495] border border-[#dcc495]/50"
                : "text-[#8492a6] hover:text-white"
            }`}
          >
            SAT
          </button>
          <button
            type="button"
            onClick={() => setMapType("TOPO")}
            className={`px-3 py-1 rounded-none transition-all cursor-pointer ${
              mapType === "TOPO"
                ? "bg-[#dcc495]/20 text-[#dcc495] border border-[#dcc495]/50"
                : "text-[#8492a6] hover:text-white"
            }`}
          >
            TOPO
          </button>
        </div>

        {/* Status Line Matching Stitch */}
        <div className="flex items-center gap-3 font-mono text-[10px] text-[#8492a6] tracking-wider">
          <span className="flex items-center gap-1.5">
            <Crosshair size={12} className="text-[#ff6b6b]" />
            <span>TRACKING 1 ENTITY</span>
          </span>
          <span className="text-[#414d5d]">·</span>
          <span className="flex items-center gap-1.5">
            <Eye size={12} className="text-[#38e8cb]" />
            <span>3 CAMERAS CORRELATED</span>
          </span>
          <span className="text-[#414d5d]">·</span>
          <span className="flex items-center gap-1.5">
            <Radio size={12} className="text-[#38e8cb]" />
            <span className="text-[#38e8cb]">PERIMETER SECURE</span>
          </span>
        </div>
      </div>
    </div>
  );
};
