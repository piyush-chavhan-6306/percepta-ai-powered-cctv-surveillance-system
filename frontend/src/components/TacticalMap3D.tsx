import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { CameraRecord, SecurityZone, VirtualBoundary, AlertItem } from '../types/surveillance';
import { Compass, Shield } from 'lucide-react';

interface TacticalMap3DProps {
  cameras: CameraRecord[];
  zones: SecurityZone[];
  boundaries: VirtualBoundary[];
  alerts: AlertItem[];
  selectedCameraId: string | null;
  onSelectCamera: (cameraId: string) => void;
}

export const TacticalMap3D: React.FC<TacticalMap3DProps> = ({
  cameras,
  zones,
  boundaries,
  alerts,
  selectedCameraId,
  onSelectCamera,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [_cameraViewMode, setCameraViewMode] = useState<'ISOMETRIC' | 'TOP_DOWN' | 'PERIMETER'>('ISOMETRIC');
  const [selectedEntity, setSelectedEntity] = useState<{ type: 'CAMERA' | 'ZONE' | 'ALERT'; id: string; name: string } | null>(null);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // 1. Scene Setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x05070a);
    scene.fog = new THREE.FogExp2(0x05070a, 0.008);

    // 2. Camera Setup
    const width = container.clientWidth;
    const height = container.clientHeight;
    const camera = new THREE.PerspectiveCamera(45, width / height, 1, 1000);
    camera.position.set(0, 70, 90);
    camera.lookAt(0, 0, 0);

    // 3. Renderer Setup
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // 4. Lighting
    const ambientLight = new THREE.AmbientLight(0x223344, 1.2);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0x00e5ff, 1.5);
    dirLight.position.set(40, 80, 40);
    scene.add(dirLight);

    const redAlertLight = new THREE.PointLight(0xff1744, 2.0, 80);
    redAlertLight.position.set(0, 15, 0);
    scene.add(redAlertLight);

    // 5. Tactical Ground Grid & Terrain
    const gridHelper = new THREE.GridHelper(140, 35, 0x00e5ff, 0x142033);
    gridHelper.position.y = 0;
    scene.add(gridHelper);

    // Subtle terrain plane
    const planeGeo = new THREE.PlaneGeometry(140, 140, 32, 32);
    const planeMat = new THREE.MeshStandardMaterial({
      color: 0x070b12,
      roughness: 0.8,
      metalness: 0.2,
      wireframe: false,
    });
    const groundMesh = new THREE.Mesh(planeGeo, planeMat);
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.position.y = -0.1;
    scene.add(groundMesh);

    // 6. Perimeter Security Line
    const borderPoints = [
      new THREE.Vector3(-60, 0.5, -20),
      new THREE.Vector3(-20, 0.5, -25),
      new THREE.Vector3(20, 0.5, -22),
      new THREE.Vector3(60, 0.5, -28),
    ];
    const borderGeo = new THREE.BufferGeometry().setFromPoints(borderPoints);
    const borderMat = new THREE.LineBasicMaterial({ color: 0xff1744, linewidth: 2 });
    const borderLine = new THREE.Line(borderGeo, borderMat);
    scene.add(borderLine);

    // 7. Radar Sweep Arc
    const radarGeo = new THREE.RingGeometry(0, 55, 32, 1, 0, Math.PI / 4);
    const radarMat = new THREE.MeshBasicMaterial({
      color: 0x00e5ff,
      transparent: true,
      opacity: 0.15,
      side: THREE.DoubleSide,
    });
    const radarMesh = new THREE.Mesh(radarGeo, radarMat);
    radarMesh.rotation.x = -Math.PI / 2;
    radarMesh.position.y = 0.2;
    scene.add(radarMesh);

    // 8. Interactive Objects Container
    const interactiveGroup = new THREE.Group();
    scene.add(interactiveGroup);

    // Camera Masts & Frustums
    const cameraObjects: THREE.Object3D[] = [];
    const defaultCoords = [
      { id: 'cam-01', x: -35, z: 15, rot: 0.3 },
      { id: 'cam-02', x: 0, z: 25, rot: 0.0 },
      { id: 'cam-03', x: 35, z: 15, rot: -0.3 },
    ];

    cameras.forEach((cam, idx) => {
      const pos = defaultCoords[idx % defaultCoords.length];
      const mastGroup = new THREE.Group();
      mastGroup.position.set(pos.x, 0, pos.z);
      mastGroup.userData = { type: 'CAMERA', id: cam.camera_id, name: cam.name };

      const isSelected = selectedCameraId === cam.camera_id;
      const mastColor = isSelected ? 0x00e5ff : (cam.status === 'online' ? 0x00e676 : 0xffab00);

      // Pole
      const poleGeo = new THREE.CylinderGeometry(0.4, 0.6, 12, 8);
      const poleMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.8, roughness: 0.3 });
      const pole = new THREE.Mesh(poleGeo, poleMat);
      pole.position.y = 6;
      mastGroup.add(pole);

      // Camera Head
      const headGeo = new THREE.BoxGeometry(2, 1.2, 3);
      const headMat = new THREE.MeshStandardMaterial({ color: mastColor, emissive: mastColor, emissiveIntensity: 0.4 });
      const head = new THREE.Mesh(headGeo, headMat);
      head.position.y = 12;
      head.rotation.y = pos.rot;
      mastGroup.add(head);

      // Viewing Frustum Cone
      const coneGeo = new THREE.ConeGeometry(14, 26, 4, 1, true);
      const coneMat = new THREE.MeshBasicMaterial({
        color: mastColor,
        wireframe: true,
        transparent: true,
        opacity: isSelected ? 0.45 : 0.15,
      });
      const cone = new THREE.Mesh(coneGeo, coneMat);
      cone.position.set(0, 6, -13);
      cone.rotation.x = Math.PI / 2 + 0.3;
      mastGroup.add(cone);

      interactiveGroup.add(mastGroup);
      cameraObjects.push(mastGroup);
    });

    // 9. Polygon Security Zones in 3D
    zones.forEach((zone, zIdx) => {
      const zoneColor = zone.severity.toLowerCase().includes('critical') || zone.severity.toLowerCase().includes('restricted') ? 0xff1744 : 0xffab00;
      const zoneGroup = new THREE.Group();
      zoneGroup.userData = { type: 'ZONE', id: zone.zone_id, name: zone.name };

      // Map 2D polygon normalized coords to 3D terrain space
      const shape = new THREE.Shape();
      const zOffset = (zIdx - 1) * 30;
      shape.moveTo(-20, -10 + zOffset);
      shape.lineTo(20, -10 + zOffset);
      shape.lineTo(15, 15 + zOffset);
      shape.lineTo(-15, 15 + zOffset);
      shape.closePath();

      const extrudeSettings = { depth: 3, bevelEnabled: false };
      const zoneGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
      const zoneMat = new THREE.MeshBasicMaterial({
        color: zoneColor,
        transparent: true,
        opacity: 0.25,
        wireframe: true,
      });
      const zoneMesh = new THREE.Mesh(zoneGeo, zoneMat);
      zoneMesh.rotation.x = -Math.PI / 2;
      zoneMesh.position.y = 0.5;
      zoneGroup.add(zoneMesh);
      interactiveGroup.add(zoneGroup);
    });

    // 10. Active Target Tracks & Threat Pulses
    const trackMarkers: THREE.Mesh[] = [];
    alerts.slice(0, 5).forEach((alert, aIdx) => {
      const x = (aIdx - 2) * 18 + (Math.sin(aIdx) * 5);
      const z = -15 + (aIdx * 6);
      
      // Marker sphere
      const sphereGeo = new THREE.SphereGeometry(1.2, 16, 16);
      const sphereMat = new THREE.MeshStandardMaterial({
        color: 0xff1744,
        emissive: 0xff1744,
        emissiveIntensity: 0.8,
      });
      const sphere = new THREE.Mesh(sphereGeo, sphereMat);
      sphere.position.set(x, 2, z);
      sphere.userData = { type: 'ALERT', id: alert.event_id, name: alert.message };
      interactiveGroup.add(sphere);
      trackMarkers.push(sphere);

      // Ground beacon ring
      const ringGeo = new THREE.RingGeometry(1.5, 3.5, 16);
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xff1744,
        transparent: true,
        opacity: 0.6,
        side: THREE.DoubleSide,
      });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.rotation.x = -Math.PI / 2;
      ring.position.set(x, 0.3, z);
      interactiveGroup.add(ring);
    });

    // 11. Mouse Interaction (Raycasting & Drag Orbit)
    let isDragging = false;
    let prevMousePos = { x: 0, y: 0 };
    let cameraAngle = 0;
    let cameraPitch = 0.6;
    let cameraDist = 110;

    const updateCameraPosition = () => {
      camera.position.x = cameraDist * Math.sin(cameraAngle) * Math.cos(cameraPitch);
      camera.position.y = cameraDist * Math.sin(cameraPitch);
      camera.position.z = cameraDist * Math.cos(cameraAngle) * Math.cos(cameraPitch);
      camera.lookAt(0, 5, 0);
    };
    updateCameraPosition();

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMousePos = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - prevMousePos.x;
      const deltaY = e.clientY - prevMousePos.y;

      cameraAngle -= deltaX * 0.006;
      cameraPitch = Math.max(0.2, Math.min(1.4, cameraPitch + deltaY * 0.006));
      updateCameraPosition();
      prevMousePos = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      cameraDist = Math.max(40, Math.min(160, cameraDist + e.deltaY * 0.08));
      updateCameraPosition();
    };

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onClick = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveGroup.children, true);

      if (intersects.length > 0) {
        let rootObj: THREE.Object3D | null = intersects[0].object;
        while (rootObj && !rootObj.userData.type && rootObj.parent) {
          rootObj = rootObj.parent;
        }

        if (rootObj && rootObj.userData.type) {
          setSelectedEntity({
            type: rootObj.userData.type,
            id: rootObj.userData.id,
            name: rootObj.userData.name,
          });

          if (rootObj.userData.type === 'CAMERA') {
            onSelectCamera(rootObj.userData.id);
          }
        }
      }
    };

    const domEl = renderer.domElement;
    domEl.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    domEl.addEventListener('wheel', onWheel, { passive: false });
    domEl.addEventListener('click', onClick);

    // 12. Animation Loop
    let animationId: number;
    const startTime = performance.now();

    const animate = () => {
      animationId = requestAnimationFrame(animate);
      const elapsed = (performance.now() - startTime) * 0.001;

      // Rotate radar sweep
      radarMesh.rotation.z = -elapsed * 1.5;

      // Pulse alert markers
      trackMarkers.forEach((m, i) => {
        m.position.y = 2 + Math.sin(elapsed * 4 + i) * 0.5;
      });

      renderer.render(scene, camera);
    };
    animate();

    // 13. Resize Handler
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      domEl.removeEventListener('mousedown', onMouseDown);
      domEl.removeEventListener('wheel', onWheel);
      domEl.removeEventListener('click', onClick);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [cameras, zones, boundaries, alerts, selectedCameraId, onSelectCamera]);

  return (
    <div className="relative w-full h-full min-h-[420px] bg-[#05070a] rounded-sm overflow-hidden border border-white/10 shadow-2xl">
      {/* 3D WebGL Canvas Mount */}
      <div ref={mountRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Top Left HUD: Tactical Sector Title & Coordinates */}
      <div className="absolute top-3 left-3 pointer-events-none flex flex-col gap-1">
        <div className="flex items-center gap-2 bg-[#0c1017]/85 backdrop-blur-md px-3 py-1.5 border border-white/10 rounded-sm">
          <Shield className="w-4 h-4 text-[#00e5ff]" />
          <span className="font-display font-bold text-sm tracking-wider text-white">SECTOR ALPHA • 3D SPATIAL PERIMETER</span>
          <span className="text-[10px] font-mono-tech px-1.5 py-0.5 bg-[#00e5ff]/20 text-[#00e5ff] rounded">REAL-TIME</span>
        </div>
        <div className="text-[10px] font-mono-tech text-gray-400 pl-1">
          COORD: 32°44'18.2"N 74°52'09.1"E • GRID: 140x140m • SENSORS: ACTIVE
        </div>
      </div>

      {/* Top Right HUD: Perspective Modes & Controls */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        <button
          onClick={() => setCameraViewMode('ISOMETRIC')}
          className="px-2.5 py-1 text-[11px] font-display font-semibold tracking-wider bg-[#0c1017]/90 hover:bg-[#141c2b] text-gray-200 border border-white/10 hover:border-[#00e5ff]/40 rounded-sm transition-all"
        >
          ISOMETRIC
        </button>
        <button
          onClick={() => setCameraViewMode('TOP_DOWN')}
          className="px-2.5 py-1 text-[11px] font-display font-semibold tracking-wider bg-[#0c1017]/90 hover:bg-[#141c2b] text-gray-200 border border-white/10 hover:border-[#00e5ff]/40 rounded-sm transition-all"
        >
          TOP-DOWN
        </button>
      </div>

      {/* Bottom Left HUD: Selected Entity Inspector */}
      {selectedEntity && (
        <div className="absolute bottom-3 left-3 bg-[#0c1017]/90 backdrop-blur-md p-3 border border-[#00e5ff]/40 rounded-sm max-w-sm">
          <div className="flex items-center justify-between gap-3 mb-1">
            <span className="text-[10px] font-mono-tech text-[#00e5ff] uppercase tracking-widest">{selectedEntity.type} SELECTED</span>
            <button onClick={() => setSelectedEntity(null)} className="text-gray-400 hover:text-white text-xs">✕</button>
          </div>
          <div className="font-display font-bold text-white text-sm">{selectedEntity.name}</div>
          <div className="text-[11px] font-mono-tech text-gray-400 truncate">ID: {selectedEntity.id}</div>
        </div>
      )}

      {/* Bottom Right HUD: 3D Legend & Compass */}
      <div className="absolute bottom-3 right-3 flex items-center gap-3 bg-[#0c1017]/85 backdrop-blur-md px-3 py-1.5 border border-white/10 rounded-sm text-[10px] font-mono-tech">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#00e676]"></span>
          <span className="text-gray-300">CAMERA (ONLINE)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#ff1744] animate-ping"></span>
          <span className="text-red-400">BREACH / ALERT</span>
        </div>
        <div className="flex items-center gap-1.5 border-l border-white/10 pl-2 text-gray-400">
          <Compass className="w-3.5 h-3.5 text-[#00e5ff]" />
          <span>NORTH 000°</span>
        </div>
      </div>
    </div>
  );
};
