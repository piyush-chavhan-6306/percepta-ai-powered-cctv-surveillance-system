import { useRef, useEffect, useCallback } from "react";

/**
 * Interactive cursor-reactive background.
 * Particles drift naturally but get gently pushed by the cursor,
 * creating a fluid, living background that responds to user movement.
 */
export function CursorReactiveBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: -9999, y: -9999, active: false });
  const particlesRef = useRef<Particle[]>([]);
  const rafRef = useRef<number>(0);

  interface Particle {
    x: number;
    y: number;
    originX: number;
    originY: number;
    vx: number;
    vy: number;
    size: number;
    baseAlpha: number;
    alpha: number;
    color: string;
    driftSpeed: number;
    driftAngle: number;
    driftRadius: number;
    phase: number;
    connected: boolean;
  }

  const PARTICLE_COUNT = 80;
  const CONNECTION_DISTANCE = 140;
  const MOUSE_RADIUS = 160;
  const MOUSE_FORCE = 2.5;

  const initParticles = useCallback((w: number, h: number) => {
    const particles: Particle[] = [];
    const colors = [
      "rgba(0, 229, 255,",
      "rgba(0, 230, 118,",
      "rgba(41, 121, 255,",
      "rgba(124, 77, 255,",
    ];

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const x = Math.random() * w;
      const y = Math.random() * h;
      particles.push({
        x,
        y,
        originX: x,
        originY: y,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 2.5 + 0.5,
        baseAlpha: Math.random() * 0.4 + 0.1,
        alpha: 0,
        color: colors[Math.floor(Math.random() * colors.length)],
        driftSpeed: Math.random() * 0.002 + 0.001,
        driftAngle: Math.random() * Math.PI * 2,
        driftRadius: Math.random() * 60 + 20,
        phase: Math.random() * Math.PI * 2,
        connected: false,
      });
    }
    return particles;
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      if (particlesRef.current.length === 0) {
        particlesRef.current = initParticles(canvas.width, canvas.height);
      }
    };
    resize();
    particlesRef.current = initParticles(canvas.width, canvas.height);
    window.addEventListener("resize", resize);

    const handleMouseMove = (e: MouseEvent) => {
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;
      mouseRef.current.active = true;
    };
    const handleMouseLeave = () => {
      mouseRef.current.active = false;
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);

    let t = 0;
    const animate = () => {
      t += 1;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const particles = particlesRef.current;
      const mx = mouseRef.current.x;
      const my = mouseRef.current.y;
      const mActive = mouseRef.current.active;

      // Update particles
      for (const p of particles) {
        // Gentle drift
        p.driftAngle += p.driftSpeed;
        const driftX = Math.cos(p.driftAngle + p.phase) * p.driftRadius * 0.01;
        const driftY = Math.sin(p.driftAngle + p.phase) * p.driftRadius * 0.01;

        // Mouse repulsion
        if (mActive) {
          const dx = p.x - mx;
          const dy = p.y - my;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MOUSE_RADIUS && dist > 0) {
            const force = (1 - dist / MOUSE_RADIUS) * MOUSE_FORCE;
            p.vx += (dx / dist) * force;
            p.vy += (dy / dist) * force;
          }
        }

        // Apply velocity with damping
        p.vx *= 0.94;
        p.vy *= 0.94;
        p.vx += driftX;
        p.vy += driftY;

        // Spring back toward origin (gentle)
        const homeX = (p.originX - p.x) * 0.002;
        const homeY = (p.originY - p.y) * 0.002;
        p.vx += homeX;
        p.vy += homeY;

        p.x += p.vx;
        p.y += p.vy;

        // Wrap around edges
        if (p.x < -20) p.x = canvas.width + 20;
        if (p.x > canvas.width + 20) p.x = -20;
        if (p.y < -20) p.y = canvas.height + 20;
        if (p.y > canvas.height + 20) p.y = -20;

        // Alpha: pulse + mouse proximity boost
        const pulse = Math.sin(t * 0.015 + p.phase) * 0.15;
        let proximityBoost = 0;
        if (mActive) {
          const dx = p.x - mx;
          const dy = p.y - my;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MOUSE_RADIUS * 1.5) {
            proximityBoost = (1 - dist / (MOUSE_RADIUS * 1.5)) * 0.5;
          }
        }
        p.alpha = Math.min(1, p.baseAlpha + pulse + proximityBoost);
      }

      // Draw connections
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i];
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.sqrt(dx * dx + dy * dy);

          if (dist < CONNECTION_DISTANCE) {
            const alpha = (1 - dist / CONNECTION_DISTANCE) * 0.12;
            // Boost connection alpha near mouse
            let mouseBoost = 0;
            if (mActive) {
              const midX = (a.x + b.x) / 2;
              const midY = (a.y + b.y) / 2;
              const mDist = Math.sqrt((midX - mx) ** 2 + (midY - my) ** 2);
              if (mDist < MOUSE_RADIUS * 1.5) {
                mouseBoost = (1 - mDist / (MOUSE_RADIUS * 1.5)) * 0.2;
              }
            }

            ctx.strokeStyle = `rgba(0, 229, 255, ${alpha + mouseBoost})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }

      // Draw particles
      for (const p of particles) {          ctx.fillStyle = `${p.color}${p.alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Draw cursor glow
      if (mActive) {
        const glowGrad = ctx.createRadialGradient(mx, my, 0, mx, my, MOUSE_RADIUS);
        glowGrad.addColorStop(0, "rgba(0, 229, 255, 0.06)");
        glowGrad.addColorStop(0.5, "rgba(0, 229, 255, 0.02)");
        glowGrad.addColorStop(1, "rgba(0, 229, 255, 0)");
        ctx.fillStyle = glowGrad;
        ctx.beginPath();
        ctx.arc(mx, my, MOUSE_RADIUS, 0, Math.PI * 2);
        ctx.fill();

        // Small bright center
        const centerGrad = ctx.createRadialGradient(mx, my, 0, mx, my, 6);
        centerGrad.addColorStop(0, "rgba(0, 229, 255, 0.3)");
        centerGrad.addColorStop(1, "rgba(0, 229, 255, 0)");
        ctx.fillStyle = centerGrad;
        ctx.beginPath();
        ctx.arc(mx, my, 6, 0, Math.PI * 2);
        ctx.fill();
      }

      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [initParticles]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.7 }}
    />
  );
}
