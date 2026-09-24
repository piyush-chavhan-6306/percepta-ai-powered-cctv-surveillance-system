import React, { useRef, useEffect } from "react";
import * as THREE from "three";

export const AuthEarthBackdrop: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 1000);
    camera.position.set(0, 0, 4.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.35;
    container.appendChild(renderer.domElement);

    // Create Procedural Earth with Night City Lights
    const globeRadius = 2.1;
    const sphereGeo = new THREE.SphereGeometry(globeRadius, 64, 64);

    // Procedural High-Res Texture with Continental Landmasses & Night City Lights
    const canvas = document.createElement("canvas");
    canvas.width = 2048;
    canvas.height = 1024;
    const ctx = canvas.getContext("2d")!;

    // Deep space ocean base
    ctx.fillStyle = "#04070a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw continent silhouettes (Americas / Atlantic orientation)
    ctx.fillStyle = "#0c151c";
    // North America
    ctx.beginPath();
    ctx.ellipse(540, 320, 260, 180, 0.2, 0, Math.PI * 2);
    ctx.fill();
    // South America
    ctx.beginPath();
    ctx.ellipse(710, 680, 190, 260, 0.35, 0, Math.PI * 2);
    ctx.fill();
    // Eurasia / Africa edge
    ctx.beginPath();
    ctx.ellipse(1400, 350, 320, 200, -0.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(1350, 620, 220, 240, 0.1, 0, Math.PI * 2);
    ctx.fill();

    // Night city light clusters (warm gold & amber specks)
    const clusterCenters = [
      { x: 550, y: 320, count: 180, spread: 120 }, // Eastern US
      { x: 440, y: 340, count: 90, spread: 90 },   // Western US
      { x: 510, y: 440, count: 70, spread: 60 },   // Mexico
      { x: 740, y: 710, count: 110, spread: 80 },  // Brazil coast
      { x: 670, y: 820, count: 60, spread: 50 },   // Argentina
      { x: 1320, y: 310, count: 160, spread: 100 }, // Western Europe
    ];

    for (const cluster of clusterCenters) {
      for (let i = 0; i < cluster.count; i++) {
        const radius = Math.random() * cluster.spread;
        const angle = Math.random() * Math.PI * 2;
        const lx = cluster.x + Math.cos(angle) * radius;
        const ly = cluster.y + Math.sin(angle) * radius * 0.75;
        const brightness = Math.random();
        
        ctx.fillStyle = brightness > 0.85 
          ? "rgba(255, 235, 180, 0.95)" 
          : brightness > 0.4 
          ? "rgba(230, 185, 110, 0.75)" 
          : "rgba(180, 140, 75, 0.4)";
        
        ctx.fillRect(lx, ly, Math.random() > 0.7 ? 2.5 : 1.5, Math.random() > 0.7 ? 2.5 : 1.5);
      }
    }

    const earthTexture = new THREE.CanvasTexture(canvas);
    earthTexture.wrapS = THREE.RepeatWrapping;
    earthTexture.wrapT = THREE.ClampToEdgeWrapping;

    // Earth Shader Material with Atmospheric Rim Lighting
    const earthMat = new THREE.ShaderMaterial({
      uniforms: {
        uTexture: { value: earthTexture },
        uSunDirection: { value: new THREE.Vector3(1.1, 0.4, 0.8).normalize() },
      },
      vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        void main() {
          vUv = uv;
          vNormal = normalize(normalMatrix * normal);
          vec4 worldPos = modelMatrix * vec4(position, 1.0);
          vWorldPosition = worldPos.xyz;
          gl_Position = projectionMatrix * viewMatrix * worldPos;
        }
      `,
      fragmentShader: `
        uniform sampler2D uTexture;
        uniform vec3 uSunDirection;
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;

        void main() {
          vec3 texColor = texture2D(uTexture, vUv).rgb;
          vec3 viewDir = normalize(cameraPosition - vWorldPosition);
          float nDotL = dot(vNormal, uSunDirection);
          
          // Atmospheric Rim Glow (Muted cyan / teal edge)
          float fresnel = 1.0 - max(0.0, dot(vNormal, viewDir));
          fresnel = pow(fresnel, 3.2);
          vec3 atmosphereGlow = vec3(0.42, 0.85, 0.88) * fresnel * 0.85;

          // Day/Night Blending with Warm City Lights on Dark Side
          float dayFactor = smoothstep(-0.2, 0.35, nDotL);
          vec3 dayColor = texColor * 1.35;
          vec3 nightColor = texColor * 1.85; // Boost night city lights
          
          vec3 finalColor = mix(nightColor, dayColor * 0.4, dayFactor) + atmosphereGlow;
          gl_FragColor = vec4(finalColor, 0.98);
        }
      `,
      transparent: true,
    });

    const earthMesh = new THREE.Mesh(sphereGeo, earthMat);
    // Position the globe slightly to the center-right, matching the reference composition
    earthMesh.position.set(0.45, -0.1, 0);
    earthMesh.rotation.x = 0.15;
    earthMesh.rotation.y = 1.45; // Face North & South America to the viewer
    scene.add(earthMesh);

    // Subtle Outer Atmosphere Halo Mesh
    const glowGeo = new THREE.SphereGeometry(globeRadius * 1.035, 48, 48);
    const glowMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        void main() {
          float intensity = pow(0.72 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 3.8);
          gl_FragColor = vec4(0.45, 0.88, 0.85, 1.0) * intensity * 0.65;
        }
      `,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      transparent: true,
    });
    const glowMesh = new THREE.Mesh(glowGeo, glowMat);
    glowMesh.position.copy(earthMesh.position);
    scene.add(glowMesh);

    // Background Subtle Stars
    const starGeo = new THREE.BufferGeometry();
    const starCount = 350;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPos[i] = (Math.random() - 0.5) * 15;
      starPos[i + 1] = (Math.random() - 0.5) * 12;
      starPos[i + 2] = -3 - Math.random() * 8;
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
      size: 0.02,
      color: 0xd6e5e3,
      transparent: true,
      opacity: 0.65,
    });
    const starPoints = new THREE.Points(starGeo, starMat);
    scene.add(starPoints);

    // Animation Loop
    let animId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      const delta = clock.getDelta();
      // Gentle, calm rotation
      earthMesh.rotation.y += delta * 0.025;
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none overflow-hidden z-0"
      style={{
        maskImage: "radial-gradient(ellipse 85% 95% at 50% 50%, black 65%, transparent 100%)",
        WebkitMaskImage: "radial-gradient(ellipse 85% 95% at 50% 50%, black 65%, transparent 100%)",
      }}
    />
  );
};
