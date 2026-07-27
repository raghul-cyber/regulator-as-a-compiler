"use client";

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Wireframe } from "@react-three/drei";
import * as THREE from "three";

function RotatingMesh() {
  const meshRef = useRef<THREE.Mesh>(null!);

  useFrame((state, delta) => {
    meshRef.current.rotation.x += delta * 0.2;
    meshRef.current.rotation.y += delta * 0.3;
  });

  return (
    <mesh ref={meshRef}>
      <icosahedronGeometry args={[1, 1]} />
      <meshBasicMaterial color="#333333" wireframe />
      {/* Subtle secondary layer */}
      <mesh scale={0.9}>
        <icosahedronGeometry args={[1, 2]} />
        <meshBasicMaterial color="#666666" wireframe opacity={0.3} transparent />
      </mesh>
    </mesh>
  );
}

export function CompilationMesh() {
  return (
    <div className="w-full h-full min-h-[300px] flex items-center justify-center relative">
      <Canvas camera={{ position: [0, 0, 3], fov: 50 }}>
        <color attach="background" args={["#000000"]} />
        <ambientLight intensity={0.5} />
        <RotatingMesh />
      </Canvas>
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="bg-black/60 px-6 py-3 rounded-full border border-gray-800 backdrop-blur-sm">
          <p className="text-sm text-gray-400 font-mono tracking-widest animate-pulse">
            COMPILING DATA...
          </p>
        </div>
      </div>
    </div>
  );
}
