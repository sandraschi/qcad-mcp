import { useEffect, useRef, useState } from "react";
import {
	AmbientLight,
	Box3,
	type BufferGeometry,
	DirectionalLight,
	Mesh,
	MeshPhongMaterial,
	PerspectiveCamera,
	Scene,
	Vector3,
	WebGLRenderer,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

interface Props {
	url: string;
}

export default function StlViewer({ url }: Props) {
	const mountRef = useRef<HTMLDivElement>(null);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState("");

	useEffect(() => {
		const mount = mountRef.current;
		if (!mount) return;

		const scene = new Scene();
		scene.background = null;

		const camera = new PerspectiveCamera(
			45,
			mount.clientWidth / mount.clientHeight,
			1,
			100000,
		);
		camera.position.set(15000, 10000, 15000);
		camera.lookAt(0, 0, 0);

		const renderer = new WebGLRenderer({ antialias: true, alpha: true });
		renderer.setPixelRatio(window.devicePixelRatio);
		renderer.setSize(mount.clientWidth, mount.clientHeight);
		renderer.setClearColor(0x000000, 0);
		mount.appendChild(renderer.domElement);

		const ambient = new AmbientLight(0x404060, 2);
		scene.add(ambient);
		const dirLight = new DirectionalLight(0xffffff, 3);
		dirLight.position.set(1, 2, 1);
		scene.add(dirLight);

		const controls = new OrbitControls(camera, renderer.domElement);
		controls.enableDamping = true;
		controls.dampingFactor = 0.08;

		const loader = new STLLoader();
		loader.load(
			url,
			(geometry: BufferGeometry) => {
				geometry.computeVertexNormals();
				const material = new MeshPhongMaterial({
					color: 0xd4a574,
					specular: 0x111111,
					shininess: 30,
					flatShading: false,
				});
				const mesh = new Mesh(geometry, material);

				geometry.computeBoundingBox();
				const bbox = geometry.boundingBox || new Box3();
				const center = new Vector3();
				bbox.getCenter(center);
				mesh.position.sub(center);
				const size = new Vector3();
				bbox.getSize(size);

				scene.add(mesh);
				setLoading(false);
				camera.position.set(size.x * 1.5, size.y * 1.2, size.z * 1.5);
			},
			undefined,
			() => {
				setLoading(false);
				setError("Failed to load STL");
			},
		);

		let animId: number;
		const animate = () => {
			animId = requestAnimationFrame(animate);
			controls.update();
			renderer.render(scene, camera);
		};
		animate();

		const handleResize = () => {
			if (!mount) return;
			camera.aspect = mount.clientWidth / mount.clientHeight;
			camera.updateProjectionMatrix();
			renderer.setSize(mount.clientWidth, mount.clientHeight);
		};
		window.addEventListener("resize", handleResize);

		return () => {
			cancelAnimationFrame(animId);
			window.removeEventListener("resize", handleResize);
			mount.removeChild(renderer.domElement);
			renderer.dispose();
		};
	}, [url]);

	return (
		<div
			ref={mountRef}
			className="w-full h-full min-h-[400px] relative rounded-2xl overflow-hidden bg-gradient-to-b from-[#1a1a24] to-[#111118]"
		>
			{loading && (
				<div className="absolute inset-0 flex items-center justify-center bg-black/20 z-10">
					<div className="text-amber-400 text-sm animate-pulse">
						Loading 3D model...
					</div>
				</div>
			)}
			{error && (
				<div className="absolute inset-0 flex items-center justify-center bg-black/20 z-10">
					<div className="text-red-400 text-sm">{error}</div>
				</div>
			)}
		</div>
	);
}
