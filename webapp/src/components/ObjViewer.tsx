import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { MTLLoader } from "three/examples/jsm/loaders/MTLLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface Props {
	url: string;
	filename?: string;
}

/** In-browser 3D preview for textured OBJ outputs: orbit with drag, zoom with wheel. */
export default function ObjViewer({ url, filename }: Props) {
	const mountRef = useRef<HTMLDivElement>(null);
	const [error, setError] = useState("");
	const [stats, setStats] = useState("");
	const label = filename ?? decodeURIComponent(url.split("/").pop() ?? "model.obj");

	useEffect(() => {
		const mount = mountRef.current;
		if (!mount) return;
		let cancelled = false;
		let renderer: THREE.WebGLRenderer | null = null;
		let controls: OrbitControls | null = null;
		let frame = 0;
		setError("");
		setStats("");

		(async () => {
			try {
				const base = url.slice(0, url.lastIndexOf("/") + 1);
				const name = decodeURIComponent(url.split("/").pop() ?? "");
				const materials = await new MTLLoader().loadAsync(base + name.replace(/\.obj$/i, ".mtl"));
				materials.preload();
				// Our UVs are world-scale tiles: repeat, don't clamp.
				for (const m of Object.values(materials.materials)) {
					const mat = m as THREE.MeshStandardMaterial;
					if (mat.map) {
						mat.map.wrapS = THREE.RepeatWrapping;
						mat.map.wrapT = THREE.RepeatWrapping;
					}
				}
				const obj = await new OBJLoader().setMaterials(materials).loadAsync(url);
				if (cancelled) return;

				const bbox = new THREE.Box3().setFromObject(obj);
				const size = new THREE.Vector3();
				bbox.getSize(size);
				const center = new THREE.Vector3();
				bbox.getCenter(center);
				obj.position.sub(center);
				const radius = Math.max(size.x, size.y, size.z) / 2;

				const w = mount.clientWidth || 600;
				const h = 420;
				renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
				renderer.setSize(w, h);
				renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
				mount.appendChild(renderer.domElement);

				const scene = new THREE.Scene();
				const camera = new THREE.PerspectiveCamera(45, w / h, 1, radius * 100);
				camera.position.set(radius * 1.6, -radius * 1.8, radius * 1.2);
				camera.up.set(0, 0, 1);

				scene.add(new THREE.HemisphereLight(0xffffff, 0x1e1e26, 1.1));
				const dir = new THREE.DirectionalLight(0xffffff, 1.6);
				dir.position.set(radius, radius, radius * 2);
				scene.add(dir);
				scene.add(obj);

				const grid = new THREE.GridHelper(Math.max(size.x, size.y) * 1.4, 20, 0x444455, 0x2a2a33);
				grid.rotation.x = Math.PI / 2;
				grid.position.z = -size.z / 2 - 1;
				scene.add(grid);

				controls = new OrbitControls(camera, renderer.domElement);
				controls.target.set(0, 0, 0);
				controls.autoRotate = true;
				controls.autoRotateSpeed = 1.2;
				controls.update();

				let tris = 0;
				obj.traverse((o) => {
					const mesh = o as THREE.Mesh;
					if (mesh.isMesh) {
						const g = mesh.geometry as THREE.BufferGeometry;
						tris += (g.index ? g.index.count : g.attributes.position.count) / 3;
					}
				});
				setStats(
					`${Math.round(tris).toLocaleString()} tris · ${size.x.toFixed(0)} x ${size.y.toFixed(0)} x ${size.z.toFixed(0)} mm`,
				);

				const animate = () => {
					if (cancelled) return;
					frame = requestAnimationFrame(animate);
					controls?.update();
					renderer?.render(scene, camera);
				};
				animate();

				const onResize = () => {
					if (!mount || !renderer) return;
					const nw = mount.clientWidth || 600;
					renderer.setSize(nw, h);
					camera.aspect = nw / h;
					camera.updateProjectionMatrix();
				};
				window.addEventListener("resize", onResize);
				(controls as OrbitControls & { __cleanup?: () => void }).__cleanup = () =>
					window.removeEventListener("resize", onResize);
			} catch (e: unknown) {
				if (!cancelled) setError(e instanceof Error ? e.message : String(e));
			}
		})();

		return () => {
			cancelled = true;
			cancelAnimationFrame(frame);
			const cleanup = (controls as (OrbitControls & { __cleanup?: () => void }) | null)?.__cleanup;
			if (cleanup) cleanup();
			controls?.dispose();
			if (renderer) {
				renderer.dispose();
				if (renderer.domElement.parentElement === mount) mount.removeChild(renderer.domElement);
			}
			mount.innerHTML = "";
		};
	}, [url]);

	return (
		<div>
			<div ref={mountRef} className="w-full rounded-xl overflow-hidden" style={{ height: 420 }} />
			<div className="flex items-center justify-between px-1 pt-2 text-xs text-slate-400">
				<span className="font-mono truncate">{label}</span>
				{error ? <span className="text-red-400">{error}</span> : <span>{stats}</span>}
			</div>
			<p className="px-1 pt-1 text-xs text-slate-500">Drag to orbit · scroll to zoom · auto-rotates when idle</p>
		</div>
	);
}
