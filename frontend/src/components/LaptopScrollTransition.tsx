import { useRef, useState } from "react";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import { api } from "@/api/client";
import { Radio, Shield, AlertTriangle, Eye, Layers, Terminal } from "lucide-react";

export function LaptopScrollTransition() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [streamLoaded, setStreamLoaded] = useState(false);

  // Track the scroll position as this section enters and moves across viewport
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "center center"],
  });

  // Spring physics for natural momentum without jitter
  const springConfig = { stiffness: 85, damping: 26, restDelta: 0.001 };

  const rotateX = useSpring(useTransform(scrollYProgress, [0, 1], [30, 0]), springConfig);
  const scale = useSpring(useTransform(scrollYProgress, [0, 1], [0.84, 1]), springConfig);
  const translateZ = useSpring(useTransform(scrollYProgress, [0, 1], [-120, 0]), springConfig);
  const opacity = useTransform(scrollYProgress, [0, 0.4], [0.3, 1]);
  const shadowOpacity = useSpring(useTransform(scrollYProgress, [0, 1], [0.2, 0.9]), springConfig);

  const streamUrl = api.getVideoStreamUrl("CAM-01");

  return (
    <div ref={containerRef} className="py-20 sm:py-28 relative overflow-hidden flex flex-col items-center">
      {/* Background radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[650px] h-[400px] bg-primary/10 blur-[130px] rounded-full pointer-events-none" />

      <div className="text-center mb-10 px-4 relative z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-[11px] font-mono text-primary mb-3">
          <Eye className="w-3.5 h-3.5" />
          <span>LIVE 3D RECONNAISSANCE VIEWPORT</span>
        </div>
        <h2 className="text-2xl sm:text-4xl font-bold text-white tracking-tight font-mono">
          REAL-TIME EDGE PERCEPTION ON DISPLAY
        </h2>
        <p className="text-xs sm:text-sm text-muted-foreground mt-2 max-w-xl mx-auto font-mono">
          Scroll-responsive 3D terminal streaming live CCTV telemetry, YOLOv8n object bounding boxes, and perimeter triggers.
        </p>
      </div>

      {/* 3D Perspective Viewport */}
      <div style={{ perspective: 1300 }} className="w-full max-w-5xl px-4 sm:px-6 relative z-10">
        <motion.div
          style={{
            rotateX,
            scale,
            opacity,
            z: translateZ,
            transformStyle: "preserve-3d",
          }}
          className="relative mx-auto"
        >
          {/* Laptop Screen & Chassis */}
          <div className="relative rounded-2xl p-2.5 sm:p-3.5 bg-[#0f1420] border border-white/15 shadow-[0_30px_90px_rgba(0,0,0,0.9)] backdrop-blur-xl">
            {/* Webcam / Sensor Notch */}
            <div className="absolute top-2 left-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-[#060910] border border-white/15 flex items-center justify-center">
              <div className="w-1 h-1 rounded-full bg-cyan-400 animate-pulse" />
            </div>

            {/* Laptop Display (Screen Glass) */}
            <div className="rounded-xl overflow-hidden bg-[#070b12] border border-white/10 aspect-[16/10] relative flex flex-col">
              {/* Window Titlebar */}
              <div className="h-8 px-4 bg-[#090e17] border-b border-white/10 flex items-center justify-between select-none">
                {/* Traffic lights */}
                <div className="flex items-center gap-1.5">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-500/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
                </div>

                {/* URL / Terminal badge */}
                <div className="px-3 py-0.5 rounded bg-black/50 border border-white/5 text-[10px] font-mono text-gray-300 flex items-center gap-1.5">
                  <Terminal className="w-3 h-3 text-primary" />
                  <span>percepta.command-post/sector-7</span>
                </div>

                <div className="text-[9px] font-mono text-emerald-400 flex items-center gap-1.5">
                  <Radio className="w-3 h-3 animate-pulse text-emerald-400" />
                  <span>30 FPS • YOLOv8n</span>
                </div>
              </div>

              {/* Inside Display Content: Real Live MJPEG Stream */}
              <div className="relative flex-1 bg-black overflow-hidden flex items-center justify-center">
                <img
                  src={streamUrl}
                  alt="Live 3D Stream Preview"
                  onLoad={() => setStreamLoaded(true)}
                  className="w-full h-full object-cover block"
                  crossOrigin="anonymous"
                />

                {/* Tactical HUD Overlay Elements inside the laptop screen */}
                <div className="absolute top-3 left-3 bg-black/75 backdrop-blur-md px-2.5 py-1 rounded text-[10px] font-mono text-cyan-400 border border-cyan-500/30 flex items-center gap-1.5">
                  <Shield className="w-3 h-3 text-cyan-400" />
                  <span>ACTIVE RECON: SECTOR 7 NORTH</span>
                </div>

                <div className="absolute bottom-3 right-3 bg-black/75 backdrop-blur-md px-2.5 py-1 rounded text-[10px] font-mono text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span>PERIMETER MONITORED</span>
                </div>

                <div className="absolute bottom-3 left-3 bg-black/75 backdrop-blur-md px-2.5 py-1 rounded text-[10px] font-mono text-gray-300 border border-white/10 flex items-center gap-2">
                  <Layers className="w-3 h-3 text-primary" />
                  <span>1920x1080 NATIVE • ZERO LATENCY</span>
                </div>
              </div>
            </div>
          </div>

          {/* Laptop Base Stand / Hinge Shadow */}
          <div className="h-3.5 w-[90%] mx-auto bg-gradient-to-b from-[#182133] via-[#0f1522] to-[#080c14] rounded-b-xl border-x border-b border-white/15 shadow-2xl" />

          {/* Ground Contact Shadow */}
          <motion.div
            style={{ opacity: shadowOpacity }}
            className="w-[85%] h-6 mx-auto bg-black/90 blur-xl -mt-1 rounded-full"
          />
        </motion.div>
      </div>
    </div>
  );
}
