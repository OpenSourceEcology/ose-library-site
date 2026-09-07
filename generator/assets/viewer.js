import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const viewers = document.querySelectorAll("[data-stl]");

for (const node of viewers) {
  const stlUrl = node.dataset.stl;
  const dimensions = JSON.parse(node.dataset.dimensions || "{}");
  node.textContent = "";

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0xfbfaf7);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10000);
  camera.up.set(0, 0, 1);
  camera.position.set(120, -180, 120);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  node.appendChild(renderer.domElement);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8578, 2.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.7);
  key.position.set(90, -120, 180);
  scene.add(key);

  const readout = document.createElement("div");
  readout.className = "viewer-readout";
  readout.textContent = `Envelope ${dimensions.x || "?"} x ${dimensions.y || "?"} x ${dimensions.z || "?"} in`;
  Object.assign(readout.style, {
    position: "absolute",
    left: "12px",
    bottom: "12px",
    padding: "6px 8px",
    border: "1px solid #21201c",
    background: "#fbfaf7",
    font: "12px IBM Plex Mono, monospace",
  });
  node.appendChild(readout);

  new STLLoader().load(stlUrl, (geometry) => {
    geometry.computeBoundingBox();
    geometry.center();
    const material = new THREE.MeshStandardMaterial({
      color: 0xb3391f,
      roughness: 0.74,
      metalness: 0.04,
    });
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const box = new THREE.Box3().setFromObject(mesh);
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 1);
    camera.position.set(maxDim * 1.2, -maxDim * 1.8, maxDim * 1.1);
    camera.near = maxDim / 100;
    camera.far = maxDim * 100;
    camera.updateProjectionMatrix();
    controls.update();
  });

  const resize = () => {
    const rect = node.getBoundingClientRect();
    renderer.setSize(rect.width, rect.height);
    camera.aspect = rect.width / Math.max(rect.height, 1);
    camera.updateProjectionMatrix();
  };

  const animate = () => {
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  };

  resize();
  animate();
  window.addEventListener("resize", resize);
}
