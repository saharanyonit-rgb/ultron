/**
 * JARVIS — Holographic core orb (Three.js scene).
 *
 * Adapted from the Ultron Orb UI by Sagar Tamang (MIT, see
 * THIRD_PARTY_NOTICES.md). The upstream version is a React component inside a
 * Next.js app; this is a framework-free port so it can mount inside the
 * existing JARVIS HUD. Scene construction, geometry, shaders, palette,
 * materials, animation constants, controls, bloom and the post-processing
 * chain are the upstream values, unmodified, so the orb looks the same.
 *
 * Local changes — deliberately minimal, none of them affect appearance:
 *  - WebGL initialisation is guarded: a missing/blocked context returns a
 *    failure result instead of throwing, so JARVIS keeps working without a GPU.
 *  - `setState()` / `setLoad()` are a thin adapter that records the JARVIS
 *    core state and machine load. They do not feed the scene: the orb renders
 *    identically in every JARVIS state, exactly as the GitHub UI does.
 *  - Detail counts are read from an optional `options.detail` with the
 *    upstream numbers as the default.
 */

// @ts-nocheck
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

const HOME_POSITION = new THREE.Vector3(0, 0.5, 5.5);
const MIN_DISTANCE = 0.6;
const MAX_DISTANCE = 40;

/** Full-detail budgets, used when the device reports a comfortable GPU. */
const DETAIL = {
  text: { outer: 1200, inner: 100, ambient: 400 },
  debris: 250,
  dust: 2000,
  panels: 30,
  secondary: 28,
};

/**
 * JARVIS core states the adapter accepts. These are the exact states already
 * produced by ui/hud-core.js — nothing new is invented here.
 */
const CORE_STATES = ['idle', 'listening', 'processing', 'executing', 'speaking', 'error', 'offline'];

export function createOrbScene(container, options = {}) {
  const width = Math.max(1, container.clientWidth);
  const height = Math.max(1, container.clientHeight);

  // ——— WEBGL GUARD ———
  // A missing or blocked context must never take JARVIS down with it.
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true });
  } catch (err) {
    return { ok: false, reason: 'WEBGL UNAVAILABLE', error: err };
  }
  if (!renderer || !renderer.getContext()) {
    return { ok: false, reason: 'WEBGL CONTEXT BLOCKED' };
  }

  // ——— SCENE ———
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 500);
  camera.position.copy(HOME_POSITION);

  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.8;
  container.appendChild(renderer.domElement);

  // ——— POST PROCESSING ———
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));

  const bloom = new UnrealBloomPass(
    new THREE.Vector2(width, height),
    1.8, // strength
    0.4, // radius
    0.2, // threshold
  );
  composer.addPass(bloom);

  // Chromatic aberration + colour grade
  const chromaticShader = {
    uniforms: {
      tDiffuse: { value: null },
      uTime: { value: 0 },
      uIntensity: { value: 0.003 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D tDiffuse;
      uniform float uTime;
      uniform float uIntensity;
      varying vec2 vUv;
      void main() {
        vec2 dir = vUv - vec2(0.5);
        float d = length(dir);
        float offset = uIntensity * d;
        float flicker = 1.0 + 0.02 * sin(uTime * 30.0) * sin(uTime * 7.3);
        vec4 cr = texture2D(tDiffuse, vUv + dir * offset);
        vec4 cg = texture2D(tDiffuse, vUv);
        vec4 cb = texture2D(tDiffuse, vUv - dir * offset * 0.5);
        gl_FragColor = vec4(cr.r, cg.g * 1.05, cb.b * 0.6, 1.0) * flicker;
        gl_FragColor.rgb = mix(gl_FragColor.rgb, gl_FragColor.rgb * vec3(1.15, 0.85, 0.55), 0.3);
      }
    `,
  };
  const chromaticPass = new ShaderPass(chromaticShader);
  composer.addPass(chromaticPass);

  // Controls: drag to rotate, scroll to zoom.
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.04;
  controls.minDistance = MIN_DISTANCE;
  controls.maxDistance = MAX_DISTANCE;
  controls.zoomSpeed = 1.4;
  controls.enablePan = false;

  // ——— COLORS ———
  const C_BRIGHT = 0xffaa30;
  const C_MID = 0xdd7700;
  const C_DIM = 0x884400;
  const C_FAINT = 0x553300;
  const C_HOT = 0xffcc66;

  const detail = options.detail || DETAIL;

  const orbGroup = new THREE.Group();
  scene.add(orbGroup);

  function lineMat(color, opacity = 1) {
    return new THREE.LineBasicMaterial({
      color,
      transparent: true,
      opacity,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
  }

  function latRing(radius, lat, segs = 120) {
    const r = radius * Math.cos(lat);
    const y = radius * Math.sin(lat);
    const pts = [];
    for (let i = 0; i <= segs; i += 1) {
      const a = (i / segs) * Math.PI * 2;
      pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  function meridian(radius, lon, segs = 120) {
    const pts = [];
    for (let i = 0; i <= segs; i += 1) {
      const lat = (i / segs) * Math.PI - Math.PI / 2;
      pts.push(new THREE.Vector3(
        radius * Math.cos(lat) * Math.cos(lon),
        radius * Math.sin(lat),
        radius * Math.cos(lat) * Math.sin(lon),
      ));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }

  // ══════════ LAYER 1: OUTER SHELL ══════════
  const outerShell = new THREE.Group();
  const R1 = 2.0;

  for (let i = -15; i <= 15; i += 1) {
    const lat = (i / 15) * (Math.PI / 2) * 0.95;
    const opacity = i % 3 === 0 ? 0.5 : 0.12;
    const color = i % 3 === 0 ? C_MID : C_FAINT;
    outerShell.add(new THREE.Line(latRing(R1, lat), lineMat(color, opacity)));
  }

  for (let i = 0; i < 24; i += 1) {
    const lon = (i / 24) * Math.PI * 2;
    const isMajor = i % 6 === 0;
    outerShell.add(new THREE.Line(
      meridian(R1, lon),
      lineMat(isMajor ? C_MID : C_FAINT, isMajor ? 0.6 : 0.1),
    ));
  }

  const CROSS_LINES = 18;
  const CROSS_SPREAD = 0.25;
  for (let i = 0; i < 4; i += 1) {
    const lon = (i / 4) * Math.PI * 2;
    for (let j = 0; j < CROSS_LINES; j += 1) {
      const t = (j / (CROSS_LINES - 1)) * 2 - 1;
      const offset = (t * CROSS_SPREAD) / 2;
      const falloff = 1 - Math.abs(t) * 0.7;
      const opacity = 0.85 * falloff;
      const color = Math.abs(t) < 0.3 ? C_BRIGHT : C_MID;
      outerShell.add(new THREE.Line(meridian(R1, lon + offset, 200), lineMat(color, opacity)));
    }
  }

  const EQ_LINES = 20;
  const EQ_SPREAD = 0.35;
  for (let j = 0; j < EQ_LINES; j += 1) {
    const t = (j / (EQ_LINES - 1)) * 2 - 1;
    const offset = (t * EQ_SPREAD) / 2;
    const falloff = 1 - Math.abs(t) * 0.65;
    const opacity = 0.8 * falloff;
    const color = Math.abs(t) < 0.3 ? C_BRIGHT : C_MID;
    outerShell.add(new THREE.Line(latRing(R1, offset, 200), lineMat(color, opacity)));
  }

  orbGroup.add(outerShell);

  // ══════════ LAYER 2: GRID PANELS ══════════
  const panelGroup = new THREE.Group();

  function createSpherePanel(latCenter, lonCenter, latSpan, lonSpan, radius, divisions = 4) {
    const group = new THREE.Group();
    const mat = lineMat(C_DIM, 0.25);

    for (let i = 0; i <= divisions; i += 1) {
      const lat = latCenter - latSpan / 2 + (i / divisions) * latSpan;
      const pts = [];
      for (let j = 0; j <= divisions * 4; j += 1) {
        const lon = lonCenter - lonSpan / 2 + (j / (divisions * 4)) * lonSpan;
        pts.push(new THREE.Vector3(
          radius * Math.cos(lat) * Math.cos(lon),
          radius * Math.sin(lat),
          radius * Math.cos(lat) * Math.sin(lon),
        ));
      }
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }

    for (let j = 0; j <= divisions; j += 1) {
      const lon = lonCenter - lonSpan / 2 + (j / divisions) * lonSpan;
      const pts = [];
      for (let i = 0; i <= divisions * 4; i += 1) {
        const lat = latCenter - latSpan / 2 + (i / (divisions * 4)) * latSpan;
        pts.push(new THREE.Vector3(
          radius * Math.cos(lat) * Math.cos(lon),
          radius * Math.sin(lat),
          radius * Math.cos(lat) * Math.sin(lon),
        ));
      }
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), mat));
    }

    return group;
  }

  for (let i = 0; i < detail.panels; i += 1) {
    const lat = (Math.random() - 0.5) * Math.PI * 0.8;
    const lon = Math.random() * Math.PI * 2;
    const size = 0.15 + Math.random() * 0.25;
    panelGroup.add(createSpherePanel(
      lat, lon, size, size, R1 + 0.01, 3 + Math.floor(Math.random() * 3),
    ));
  }
  orbGroup.add(panelGroup);

  // ══════════ LAYER 3: SECONDARY SHELL ══════════
  const shell2 = new THREE.Group();
  const R2 = 2.12;
  const secondaryCount = Math.round(detail.secondary / 2);

  for (let i = 0; i < secondaryCount; i += 1) {
    const lat = (Math.random() - 0.5) * Math.PI * 0.85;
    const startLon = Math.random() * Math.PI * 2;
    const arcLen = 0.3 + Math.random() * 1.2;
    const pts = [];
    const segs = 60;
    const r = R2 * Math.cos(lat);
    const y = R2 * Math.sin(lat);
    for (let j = 0; j <= segs; j += 1) {
      const a = startLon + (j / segs) * arcLen;
      pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
    }
    shell2.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      lineMat(C_MID, 0.2 + Math.random() * 0.3),
    ));
  }

  for (let i = 0; i < secondaryCount; i += 1) {
    const lon = Math.random() * Math.PI * 2;
    const startLat = (Math.random() - 0.5) * Math.PI * 0.8;
    const arcLen = 0.3 + Math.random() * 0.8;
    const pts = [];
    const segs = 40;
    for (let j = 0; j <= segs; j += 1) {
      const lat = startLat + (j / segs) * arcLen;
      pts.push(new THREE.Vector3(
        R2 * Math.cos(lat) * Math.cos(lon),
        R2 * Math.sin(lat),
        R2 * Math.cos(lat) * Math.sin(lon),
      ));
    }
    shell2.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      lineMat(C_DIM, 0.15 + Math.random() * 0.2),
    ));
  }
  orbGroup.add(shell2);

  // ══════════ LAYER 4: INNER CORE ══════════
  const innerCore = new THREE.Group();
  const R3 = 0.9;

  for (let s = 0; s < 8; s += 1) {
    const pts = [];
    const turns = 3 + Math.random() * 2;
    const segs = 300;
    const phase = (s / 8) * Math.PI * 2;
    for (let i = 0; i <= segs; i += 1) {
      const t = i / segs;
      const lat = t * Math.PI - Math.PI / 2;
      const lon = t * turns * Math.PI * 2 + phase;
      pts.push(new THREE.Vector3(
        R3 * Math.cos(lat) * Math.cos(lon),
        R3 * Math.sin(lat),
        R3 * Math.cos(lat) * Math.sin(lon),
      ));
    }
    innerCore.add(new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      lineMat(C_BRIGHT, 0.3 + Math.random() * 0.2),
    ));
  }

  for (let i = -6; i <= 6; i += 1) {
    const lat = (i / 6) * (Math.PI / 2) * 0.9;
    innerCore.add(new THREE.Line(latRing(R3, lat, 80), lineMat(C_DIM, 0.2)));
  }

  for (let i = 0; i < 12; i += 1) {
    const lon = (i / 12) * Math.PI * 2;
    innerCore.add(new THREE.Line(meridian(R3, lon, 80), lineMat(C_DIM, 0.15)));
  }

  orbGroup.add(innerCore);

  // ══════════ LAYER 5: INNERMOST CORE ══════════
  const coreR = 0.25;
  const icoGeo = new THREE.IcosahedronGeometry(coreR, 1);
  const icoWireMat = lineMat(C_HOT, 0.9);
  const icoWire = new THREE.LineSegments(new THREE.EdgesGeometry(icoGeo), icoWireMat);
  orbGroup.add(icoWire);

  const coreSphereMat = new THREE.MeshBasicMaterial({
    color: C_HOT,
    transparent: true,
    opacity: 0.15,
    blending: THREE.AdditiveBlending,
  });
  const coreSphere = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), coreSphereMat);
  orbGroup.add(coreSphere);

  const glowSphereMat = new THREE.MeshBasicMaterial({
    color: C_MID,
    transparent: true,
    opacity: 0.04,
    blending: THREE.AdditiveBlending,
  });
  const glowSphere = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 16), glowSphereMat);
  orbGroup.add(glowSphere);

  // ══════════ CODE TEXT ══════════
  const codeSnippets = [
    'sys.init()', '0xFF3A', 'malloc()', '>> SCAN', 'void*', 'ACK',
    'SYNC OK', 'ptr_ref', 'exec()', 'hash256', '::bind', 'core.0',
    '01101001', '10110100', '>>> RDY', 'HEAP 4K', 'TCP/SYN',
    'mutex.lk', 'IRQ 0x7', 'DMA xfer', 'REG EAX', 'FAULT 0',
    'kernel.d', 'pipe |>', 'chmod +x', 'fork()', 'SIGTERM',
    'eth0: UP', 'AES-256', 'RSA 4096', 'TLS 1.3', 'HTTP/2',
    'latency', '200 OK', 'PATCH /', 'fn main', 'use std',
    'impl Orb', 'async {}', 'spawn()', 'arc::new', '.unwrap',
  ];

  function makeTextSprite(text, size = 0.08) {
    const c = document.createElement('canvas');
    c.width = 256;
    c.height = 32;
    const ctx = c.getContext('2d');
    if (!ctx) return new THREE.Object3D();
    ctx.font = 'bold 14px Courier New';
    const alpha = 0.35 + Math.random() * 0.55;
    ctx.fillStyle = `rgba(255, ${(130 + Math.random() * 80) | 0}, ${(20 + Math.random() * 30) | 0}, ${alpha})`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 128, 16);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    const s = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }));
    s.scale.set(size * 5, size * 0.7, 1);
    return s;
  }

  function scatterText(count, sizeFn, rFn, speedScale) {
    const group = new THREE.Group();
    for (let i = 0; i < count; i += 1) {
      const sp = makeTextSprite(codeSnippets[Math.floor(Math.random() * codeSnippets.length)], sizeFn());
      const phi = Math.acos(2 * Math.random() - 1);
      const theta = Math.random() * Math.PI * 2;
      const r = rFn();
      sp.position.set(
        r * Math.sin(phi) * Math.cos(theta),
        r * Math.cos(phi),
        r * Math.sin(phi) * Math.sin(theta),
      );
      sp.userData = {
        phi,
        theta,
        r,
        speed: (speedScale[0] + Math.random() * speedScale[1]) * (Math.random() > 0.5 ? 1 : -1),
      };
      group.add(sp);
    }
    return group;
  }

  const textOuter = scatterText(
    detail.text.outer,
    () => 0.04 + Math.random() * 0.04,
    () => R1 + 0.03 + Math.random() * 0.08,
    [0.0002, 0.0008],
  );
  orbGroup.add(textOuter);

  const textInner = scatterText(
    detail.text.inner,
    () => 0.03 + Math.random() * 0.03,
    () => R3 + 0.02,
    [0.0005, 0.001],
  );
  orbGroup.add(textInner);

  const textAmbient = scatterText(
    detail.text.ambient,
    () => 0.03,
    () => R3 + 0.2 + Math.random() * (R1 - R3 - 0.3),
    [0.0003, 0.0006],
  );
  orbGroup.add(textAmbient);

  // ══════════ ORBITING DEBRIS ══════════
  const debrisGeos = [
    new THREE.IcosahedronGeometry(0.012, 0),
    new THREE.IcosahedronGeometry(0.02, 0),
    new THREE.IcosahedronGeometry(0.03, 1),
    new THREE.IcosahedronGeometry(0.008, 0),
    new THREE.TetrahedronGeometry(0.015, 0),
    new THREE.OctahedronGeometry(0.018, 0),
  ];
  const debris = [];
  for (let i = 0; i < detail.debris; i += 1) {
    const geo = debrisGeos[Math.floor(Math.random() * debrisGeos.length)];
    const mat = new THREE.MeshBasicMaterial({
      color: Math.random() > 0.7 ? C_BRIGHT : C_MID,
      transparent: true,
      opacity: 0.3 + Math.random() * 0.6,
      blending: THREE.AdditiveBlending,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const orbitR = 1.2 + Math.random() * 4.0;
    mesh.userData = {
      orbitR,
      speed: (0.08 + Math.random() * 0.6) * (Math.random() > 0.5 ? 1 : -1),
      tiltX: (Math.random() - 0.5) * Math.PI * 0.9,
      tiltZ: (Math.random() - 0.5) * Math.PI * 0.5,
      phase: Math.random() * Math.PI * 2,
    };
    debris.push(mesh);
    orbGroup.add(mesh);

    if (Math.random() > 0.85) {
      const trailPts = [];
      for (let j = 0; j <= 15; j += 1) {
        const a = -(j / 15) * 0.3;
        trailPts.push(new THREE.Vector3(
          orbitR * Math.cos(a + mesh.userData.phase),
          orbitR * 0.08 * Math.sin(a * 3),
          orbitR * Math.sin(a + mesh.userData.phase),
        ));
      }
      mesh.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(trailPts),
        lineMat(C_FAINT, 0.08),
      ));
    }
  }

  // ══════════ DUST ══════════
  const dustCount = detail.dust;
  const dustPos = new Float32Array(dustCount * 3);
  for (let i = 0; i < dustCount; i += 1) {
    const rr = 0.5 + Math.pow(Math.random(), 0.6) * 7;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    dustPos[i * 3] = rr * Math.sin(phi) * Math.cos(theta);
    dustPos[i * 3 + 1] = rr * Math.cos(phi);
    dustPos[i * 3 + 2] = rr * Math.sin(phi) * Math.sin(theta);
  }
  const dustGeo = new THREE.BufferGeometry();
  dustGeo.setAttribute('position', new THREE.Float32BufferAttribute(dustPos, 3));

  const dotC = document.createElement('canvas');
  dotC.width = 64;
  dotC.height = 64;
  const dCtx = dotC.getContext('2d');
  if (dCtx) {
    const g = dCtx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, 'rgba(255,170,48,1)');
    g.addColorStop(0.2, 'rgba(255,120,20,0.6)');
    g.addColorStop(0.5, 'rgba(200,80,0,0.15)');
    g.addColorStop(1, 'rgba(100,40,0,0)');
    dCtx.fillStyle = g;
    dCtx.fillRect(0, 0, 64, 64);
  }

  const dustMat = new THREE.PointsMaterial({
    map: new THREE.CanvasTexture(dotC),
    size: 0.04,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    sizeAttenuation: true,
    color: C_BRIGHT,
  });
  const dustPoints = new THREE.Points(dustGeo, dustMat);
  orbGroup.add(dustPoints);

  // ══════════ SCANNING RINGS ══════════
  function makeScanRing(radius, thickness = 0.015) {
    const geo = new THREE.RingGeometry(radius - thickness, radius + thickness, 120);
    const mat = new THREE.MeshBasicMaterial({
      color: C_BRIGHT,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.rotation.x = Math.PI / 2;
    return mesh;
  }

  const scanRing1 = makeScanRing(R1, 0.01);
  const scanRing2 = makeScanRing(R1 * 0.7, 0.008);
  orbGroup.add(scanRing1, scanRing2);

  // ══════════ HEXAGONAL NODES ══════════
  for (let i = 0; i < 15; i += 1) {
    const phi = Math.acos(2 * Math.random() - 1);
    const theta = Math.random() * Math.PI * 2;
    const r = R1 + 0.02;
    const hexGeo = new THREE.CircleGeometry(0.03 + Math.random() * 0.02, 6);
    const hex = new THREE.LineSegments(new THREE.EdgesGeometry(hexGeo), lineMat(C_MID, 0.5));
    hex.position.set(
      r * Math.sin(phi) * Math.cos(theta),
      r * Math.cos(phi),
      r * Math.sin(phi) * Math.sin(theta),
    );
    hex.lookAt(0, 0, 0);
    outerShell.add(hex);
  }

  // ══════════ PROGRAMMATIC CAMERA CONTROL ══════════
  const sphericalScratch = new THREE.Spherical();
  const offsetScratch = new THREE.Vector3();

  function rotateBy(deltaTheta, deltaPhi) {
    offsetScratch.copy(camera.position).sub(controls.target);
    sphericalScratch.setFromVector3(offsetScratch);
    sphericalScratch.theta -= deltaTheta;
    sphericalScratch.phi = THREE.MathUtils.clamp(
      sphericalScratch.phi - deltaPhi,
      0.05,
      Math.PI - 0.05,
    );
    sphericalScratch.makeSafe();
    offsetScratch.setFromSpherical(sphericalScratch);
    camera.position.copy(controls.target).add(offsetScratch);
    camera.lookAt(controls.target);
  }

  function zoomBy(factor) {
    offsetScratch.copy(camera.position).sub(controls.target);
    const dist = THREE.MathUtils.clamp(
      offsetScratch.length() * factor,
      MIN_DISTANCE,
      MAX_DISTANCE,
    );
    offsetScratch.setLength(dist);
    camera.position.copy(controls.target).add(offsetScratch);
  }

  function resetView() {
    camera.position.copy(HOME_POSITION);
    controls.target.set(0, 0, 0);
    camera.lookAt(controls.target);
    controls.update();
  }

  // ══════════ JARVIS ADAPTER (state tracking only) ══════════
  // JARVIS already publishes a core state and a machine-load figure. The orb
  // records them so the HUD and telemetry stay in step, but it deliberately
  // does NOT feed them into the scene: every geometry, colour, rotation speed
  // and bloom value below is the upstream Ultron value, unmodified, so the orb
  // looks exactly like the GitHub UI in every state.
  let currentState = 'idle';
  let load = 0;

  function setState(next) {
    currentState = CORE_STATES.includes(next) ? next : 'idle';
  }

  function setLoad(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
      load = Math.min(1, Math.max(0, value));
    }
  }

  function getState() {
    return currentState;
  }

  // ══════════ ANIMATION ══════════
  // Upstream timing: THREE.Clock + getElapsedTime().
  const clock = new THREE.Clock();
  let flickerTimer = 0;
  let rafId = 0;
  let disposed = false;

  function animate() {
    if (disposed) return;
    rafId = requestAnimationFrame(animate);
    const t = clock.getElapsedTime();

    outerShell.rotation.y += 0.0015;
    outerShell.rotation.x = Math.sin(t * 0.08) * 0.05;

    panelGroup.rotation.y += 0.0018;
    panelGroup.rotation.x = Math.sin(t * 0.08 + 0.5) * 0.04;

    shell2.rotation.y -= 0.001;
    shell2.rotation.z = Math.sin(t * 0.12) * 0.03;

    innerCore.rotation.y -= 0.005;
    innerCore.rotation.z += 0.002;
    innerCore.rotation.x = Math.cos(t * 0.1) * 0.08;

    icoWire.rotation.x += 0.008;
    icoWire.rotation.y += 0.012;

    // Core pulse — dramatic surges but mostly transparent
    const wave1 = Math.sin(t * 1.2);
    const wave3 = Math.pow(Math.max(0, Math.sin(t * 0.4)), 5);
    const wave4 = Math.pow(Math.max(0, Math.sin(t * 0.7 + 2)), 8);
    const fadeOut = Math.pow(Math.max(0, Math.sin(t * 0.25)), 3);
    const surge = wave3 * 1.5 + wave4 * 2.0;
    const coreScale = 1 + surge + Math.sin(t * 5) * 0.05;
    coreSphere.scale.setScalar(coreScale);
    // Opacity: mostly very low (0-0.15), sometimes fully transparent, brief bright on surge
    const coreOpacity = Math.max(
      0,
      (0.08 + wave1 * 0.05 + surge * 0.2) * (1 - fadeOut * 0.95),
    );
    coreSphereMat.opacity = Math.min(0.6, coreOpacity);
    glowSphere.scale.setScalar(1 + surge * 0.8);
    glowSphereMat.opacity = Math.max(0, (0.03 + surge * 0.08) * (1 - fadeOut * 0.9));
    // Icosahedron wireframe stays visible even when glow fades
    icoWire.scale.setScalar(1 + surge * 0.6);
    icoWireMat.opacity = Math.min(1, 0.5 + surge * 0.4);

    debris.forEach((d) => {
      const u = d.userData;
      const a = t * u.speed + u.phase;
      d.position.set(
        u.orbitR * Math.cos(a) * Math.cos(u.tiltX),
        u.orbitR * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(a * 0.3 + u.tiltZ) * 0.2,
        u.orbitR * Math.sin(a) * Math.cos(u.tiltZ),
      );
      d.rotation.x += 0.015;
      d.rotation.z += 0.01;
    });

    const driftGroups = [[textOuter, 1], [textInner, 2], [textAmbient, 1.2]];
    for (const [group, mult] of driftGroups) {
      group.children.forEach((sp) => {
        const u = sp.userData;
        u.theta += u.speed * mult;
        sp.position.set(
          u.r * Math.sin(u.phi) * Math.cos(u.theta),
          u.r * Math.cos(u.phi),
          u.r * Math.sin(u.phi) * Math.sin(u.theta),
        );
      });
    }

    // Scan rings sweeping
    const scanY1 = Math.sin(t * 0.4) * R1;
    scanRing1.position.y = scanY1;
    const scanS1 = Math.sqrt(Math.max(0, R1 * R1 - scanY1 * scanY1)) / R1;
    scanRing1.scale.set(scanS1, scanS1, 1);
    scanRing1.material.opacity = 0.2 * scanS1;

    const scanY2 = Math.sin(t * 0.6 + 2) * R3;
    scanRing2.position.y = scanY2;
    const scanS2 = Math.sqrt(Math.max(0, R3 * R3 - scanY2 * scanY2)) / R3;
    scanRing2.scale.set(scanS2, scanS2, 1);
    scanRing2.material.opacity = 0.15 * scanS2;

    // Dust rotation
    dustPoints.rotation.y += 0.0002;

    // Random flicker on some panels
    flickerTimer += 0.016;
    if (flickerTimer > 0.1) {
      flickerTimer = 0;
      panelGroup.children.forEach((p) => {
        if (Math.random() > 0.95) p.visible = !p.visible;
      });
    }

    // Bloom pulse
    bloom.strength = 1.6 + Math.sin(t * 0.8) * 0.3;

    // Update chromatic aberration time
    chromaticPass.uniforms.uTime.value = t;

    controls.update();
    composer.render();
  }

  animate();

  function onResize() {
    const w = Math.max(1, container.clientWidth);
    const h = Math.max(1, container.clientHeight);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    composer.setSize(w, h);
  }
  window.addEventListener('resize', onResize);

  function dispose() {
    disposed = true;
    cancelAnimationFrame(rafId);
    window.removeEventListener('resize', onResize);
    controls.dispose();
    scene.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose();
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const mat of mats) {
        if (!mat) continue;
        if (mat.map) mat.map.dispose();
        mat.dispose();
      }
    });
    composer.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  }

  return {
    ok: true,
    rotateBy,
    zoomBy,
    zoomIn: () => zoomBy(0.65),
    zoomOut: () => zoomBy(1.55),
    resetView,
    setState,
    setLoad,
    getState,
    dispose,
  };
}
