"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger);

const PIN_VH_MULTIPLE = 1.0; // Compact scroll multiple — eliminates the giant empty void
const IMMERSE_OVERFILL = 1.02;
const ENTRY_DELAY = 0.15;
const CARD_START_SCALE_DESKTOP = 0.72;
const CARD_START_SCALE_MOBILE = 0.88;

export type BorderWatchHeroProps = {
  frameCount: number;
  frameUrl: (index: number) => string;
  titleTop: string;
  titleBottom: string;
  bgClassName?: string;
  accentHex?: string;
  defaultAspect?: number;
  onLaunchConsole?: () => void;
};

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(mq.matches);
    update();
    mq.addEventListener?.("change", update);
    return () => mq.removeEventListener?.("change", update);
  }, []);
  return reduced;
}

export function BorderWatchHero({
  frameCount,
  frameUrl,
  titleTop,
  titleBottom,
  bgClassName = "bg-black",
  accentHex = "#0e2a3d",
  defaultAspect = 16 / 9,
  onLaunchConsole,
}: BorderWatchHeroProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imagesRef = useRef<HTMLImageElement[]>([]);
  const lastDrawnRef = useRef<number>(-1);
  const bgRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const titleTopRef = useRef<HTMLHeadingElement>(null);
  const titleBottomRef = useRef<HTMLHeadingElement>(null);

  const [ready, setReady] = useState(false);
  const [framesOk, setFramesOk] = useState(true);
  const [aspect, setAspect] = useState<number>(defaultAspect);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (reduced) return;
    let cancelled = false;
    let errored = 0;
    const images: HTMLImageElement[] = new Array(frameCount);
    imagesRef.current = images;

    const onFirstReady = (img: HTMLImageElement) => {
      if (cancelled) return;
      const canvas = canvasRef.current;
      if (canvas && img.naturalWidth && img.naturalHeight) {
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        const ctx = canvas.getContext("2d");
        ctx?.drawImage(img, 0, 0);
        lastDrawnRef.current = 0;
        setAspect(img.naturalWidth / img.naturalHeight);
      }
      setReady(true);
    };

    const onErr = () => {
      errored++;
      if (!cancelled && errored >= 5) setFramesOk(false);
    };

    const loadOne = (i: number) => {
      const img = new window.Image();
      img.decoding = "async";
      if (i < 4)
        (img as HTMLImageElement & { fetchPriority?: string }).fetchPriority = "high";
      img.onerror = onErr;
      if (i === 0) img.onload = () => onFirstReady(img);
      img.src = frameUrl(i);
      images[i] = img;
    };

    const INITIAL = Math.min(20, frameCount);
    for (let i = 0; i < INITIAL; i++) loadOne(i);

    const BATCH = 20;
    let cursor = INITIAL;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const loadNext = () => {
      if (cancelled) return;
      const end = Math.min(frameCount, cursor + BATCH);
      for (let i = cursor; i < end; i++) loadOne(i);
      cursor = end;
      if (cursor < frameCount) timer = setTimeout(loadNext, 80);
    };
    timer = setTimeout(loadNext, 200);

    const fallbackTimer = window.setTimeout(() => {
      if (!cancelled && !images[0]?.complete) setFramesOk(false);
    }, 3000);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      window.clearTimeout(fallbackTimer);
    };
  }, [reduced, frameCount, frameUrl]);

  useEffect(() => {
    if (reduced) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ delay: ENTRY_DELAY });
      tl.from(bgRef.current, { opacity: 0, duration: 1.0, ease: "power2.out" });
      tl.from(cardRef.current, { opacity: 0, duration: 0.9, ease: "power3.out" }, 0.2);
      tl.from(titleTopRef.current, { opacity: 0, y: 20, duration: 0.8, ease: "expo.out" }, 0.3);
      tl.from(titleBottomRef.current, { opacity: 0, y: -20, duration: 0.8, ease: "expo.out" }, 0.4);
    }, sectionRef);
    return () => ctx.revert();
  }, [reduced]);

  useEffect(() => {
    if (reduced || !ready || !framesOk) return;
    const section = sectionRef.current;
    if (!section) return;

    const ctx = gsap.context(() => {
      const startScale = () =>
        window.innerWidth < 768 ? CARD_START_SCALE_MOBILE : CARD_START_SCALE_DESKTOP;

      const immerseScale = () => {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const baseW = Math.min(vw * 0.94, vh * 0.65 * aspect);
        const baseH = Math.min(vh * 0.65, (vw * 0.94) / aspect);
        if (baseW <= 0 || baseH <= 0) return 1.3;
        return Math.max(vw / baseW, vh / baseH) * IMMERSE_OVERFILL;
      };

      const isLoaded = (i: number) => {
        const img = imagesRef.current[i];
        return !!img && img.complete && img.naturalWidth > 0;
      };

      const drawFrame = (index: number) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        let useIdx = index;
        if (!isLoaded(useIdx)) {
          let found = -1;
          for (let d = 1; d < frameCount; d++) {
            if (useIdx - d >= 0 && isLoaded(useIdx - d)) { found = useIdx - d; break; }
            if (useIdx + d < frameCount && isLoaded(useIdx + d)) { found = useIdx + d; break; }
          }
          if (found === -1) return;
          useIdx = found;
        }
        if (lastDrawnRef.current === useIdx) return;
        const img = imagesRef.current[useIdx];
        const ctx2 = canvas.getContext("2d");
        if (!ctx2 || !img) return;
        ctx2.drawImage(img, 0, 0, canvas.width, canvas.height);
        lastDrawnRef.current = useIdx;
      };

      gsap.set(cardRef.current, { scale: startScale(), transformOrigin: "50% 50%" });

      const master = gsap.timeline({
        scrollTrigger: {
          trigger: section,
          start: "top top",
          end: "bottom bottom",
          scrub: 0.3,
          invalidateOnRefresh: true,
          onUpdate: (self) => {
            const p = self.progress;
            const mapped = gsap.utils.clamp(0, 1, (p - 0.1) / 0.8);
            const frameIdx = Math.min(frameCount - 1, Math.floor(mapped * frameCount));
            drawFrame(frameIdx);
          },
        },
      });

      master.to(cardRef.current, { scale: 1, ease: "power2.out", duration: 0.2 }, 0);
      master.to(titleTopRef.current, {
        x: () => (window.innerWidth < 768 ? "-40vw" : "-35vw"),
        opacity: 0.3,
        ease: "power2.inOut", duration: 0.3,
      }, 0);
      master.to(titleBottomRef.current, {
        x: () => (window.innerWidth < 768 ? "40vw" : "35vw"),
        opacity: 0.3,
        ease: "power2.inOut", duration: 0.3,
      }, 0);

      master.to(cardRef.current, { scale: immerseScale(), ease: "power2.in", duration: 0.5 }, 0.2);

      ScrollTrigger.refresh();
    }, sectionRef);

    return () => ctx.revert();
  }, [ready, framesOk, reduced, aspect, frameCount]);

  const tallHeight = `${(PIN_VH_MULTIPLE + 1) * 70}vh`;

  return (
    <section
      ref={sectionRef}
      className={`relative w-full overflow-hidden text-white ${bgClassName}`}
      style={{ minHeight: tallHeight }}
      aria-label="Border surveillance hero"
    >
      <div className="relative flex min-h-[70vh] w-full flex-col items-center justify-center overflow-hidden py-8">
        <div ref={bgRef} aria-hidden className="absolute inset-0 z-0" style={{ backgroundColor: accentHex }} />
        <div aria-hidden className="absolute inset-0 z-0 bg-black/50" />
        <div aria-hidden className="absolute inset-0 z-0" style={{
          background: "radial-gradient(ellipse at 50% 35%, rgba(0,229,255,0.08) 0%, rgba(0,0,0,0) 65%)",
        }} />

        <div className="relative z-10 flex h-full w-full flex-col items-center justify-center gap-2 md:gap-3">
          <h2 ref={titleTopRef} aria-hidden className="font-orbitron font-black uppercase text-center tracking-wider text-white" style={{
            fontSize: "clamp(2rem, 5vw, 4.5rem)", lineHeight: 0.95,
          }}>
            {titleTop}
          </h2>

          <div ref={cardRef} className="relative overflow-hidden rounded-[8px] shadow-[0_20px_60px_rgba(0,0,0,0.8)] ring-1 ring-white/20 will-change-transform" style={{
            width: `min(90vw, calc(52svh * ${aspect}))`,
            height: `min(52svh, 90vw / ${aspect})`,
            aspectRatio: aspect,
          }}>
            {/* CCTV HUD Overlay */}
            <div aria-hidden className="pointer-events-none absolute inset-2.5 z-30 border border-white/20" />
            <div aria-hidden className="pointer-events-none absolute left-3 top-3 z-30 flex items-center gap-2 text-[10px] font-mono-tech uppercase tracking-widest text-white/90">
              <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              REC · SECTOR CAM 01
            </div>
            <div aria-hidden className="pointer-events-none absolute right-3 top-3 z-30 text-[10px] font-mono-tech uppercase tracking-widest text-[#00e5ff]">
              LIVE INGESTION
            </div>
            <div aria-hidden className="pointer-events-none absolute inset-0 z-20 shadow-[inset_0_0_80px_rgba(0,0,0,0.6)]" />

            {/* Video Fallback / Video player */}
            <video
              src="/videos/virat_cctv.mp4"
              autoPlay
              loop
              muted
              playsInline
              className="absolute inset-0 h-full w-full object-cover"
            />

            {framesOk && (
              <canvas ref={canvasRef} aria-hidden className="absolute inset-0 h-full w-full object-cover opacity-0 pointer-events-none" />
            )}
          </div>

          <h2 ref={titleBottomRef} aria-hidden className="font-orbitron font-black uppercase text-center tracking-wider text-[#00e5ff]" style={{
            fontSize: "clamp(2rem, 5vw, 4.5rem)", lineHeight: 0.95,
          }}>
            {titleBottom}
          </h2>

          {onLaunchConsole && (
            <button
              onClick={onLaunchConsole}
              className="mt-3 flex items-center gap-2 px-6 py-2.5 bg-[#00e5ff] hover:bg-[#33eaff] text-black font-display font-bold text-sm rounded-sm shadow-[0_0_20px_rgba(0,229,255,0.4)] transition-all cursor-pointer"
            >
              LAUNCH OPERATOR COMMAND POST
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
