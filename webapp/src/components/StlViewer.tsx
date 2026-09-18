import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

interface Props {
	url: string;
	filename?: string;
}

/** In-browser 3D preview for STL outputs: orbit with drag, zoom with wheel. */
export default function StlViewer({ url, filename }: Props) {
	const mountRef = useRef<HTMLDivElement>(null);
	const [error, setError] = useState("");
	const [stats, setStats] = useState("");
	const label = filename ?? decodeURIComponent(url.split("/").pop() ?? "model.stl");

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
				const r = await fetch(url);
				if (!r.ok) throw new Error(`HTTP ${r.status}`);
				const buf = await r.arrayBuffer();
				if (cancelled) return;
				const geo = new STLLoader().parse(buf);
				geo.computeBoundingBox();
				geo.computeBoundingSphere();
				const bb = geo.boundingBox as THREE.Box3;
				const size = new THREE.Vector3();
				bb.getSize(size);
				const center = new THREE.Vector3();
				bb.getCenter(center);
				geo.translate(-center.x, -center.y, -center.z);
				const radius = geo.boundingSphere ? geo.boundingSphere.radius : Math.max(size.x, size.y, size.z) / 2;

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

				const mat = new THREE.MeshStandardMaterial({
					color: 0xd97706,
					metalness: 0.15,
					roughness: 0.6,
					side: THREE.DoubleSide,
				});
				scene.add(new THREE.Mesh(geo, mat));

				const grid = new THREE.GridHelper(Math.max(size.x, size.y) * 1.4, 20, 0x444455, 0x2a2a33);
				grid.rotation.x = Math.PI / 2;
				grid.position.z = -size.z / 2 - 1;
				scene.add(grid);

				controls = new OrbitControls(camera, renderer.domElement);
				controls.target.set(0, 0, 0);
				controls.autoRotate = true;
				controls.autoRotateSpeed = 1.2;
				controls.update();

				setStats(
					`${(geo.attributes.position.count / 3).toLocaleString()} facets · ${size.x.toFixed(0)} x ${size.y.toFixed(0)} x ${size.z.toFixed(0)} mm`,
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
