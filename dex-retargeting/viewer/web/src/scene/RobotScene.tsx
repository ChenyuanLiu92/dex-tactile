import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import URDFLoader, { type URDFRobot } from 'urdf-loader'

export function RobotScene({ joints }: { joints: Record<string, number> | null }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const robotRef = useRef<URDFRobot | null>(null)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#0b0e11')
    const camera = new THREE.PerspectiveCamera(32, 1, 0.001, 10)
    camera.up.set(0, 0, 1)
    camera.position.set(0.42, -0.58, 0.24)
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true,
    })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2
    renderer.domElement.dataset.testid = 'robot-canvas'
    host.appendChild(renderer.domElement)

    scene.add(new THREE.HemisphereLight('#dce8f4', '#171a1e', 2.1))
    const key = new THREE.DirectionalLight('#ffffff', 3.5)
    key.position.set(1, -1, 2)
    scene.add(key)
    const rim = new THREE.DirectionalLight('#d59439', 2.2)
    rim.position.set(-1, 0.5, 0.4)
    scene.add(rim)
    const grid = new THREE.GridHelper(0.5, 25, '#3b4148', '#20252a')
    grid.rotation.x = Math.PI / 2
    grid.position.z = -0.025
    scene.add(grid)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.target.set(0, 0, 0.08)
    controls.minDistance = 0.18
    controls.maxDistance = 1.2

    const manager = new THREE.LoadingManager()
    const urdfLoader = new URDFLoader(manager)
    urdfLoader.parseCollision = false
    urdfLoader.loadMeshCb = (path, loadingManager, done) => {
      new GLTFLoader(loadingManager).load(
        path,
        (gltf) => done(gltf.scene),
        undefined,
        (error) => done(
          null as unknown as THREE.Object3D,
          error instanceof Error ? error : new Error(String(error)),
        ),
      )
    }
    urdfLoader.load('/assets/inspire_hand_right.urdf', (robot) => {
      robot.traverse((object) => {
        if (!(object instanceof THREE.Mesh)) return
        const material = new THREE.MeshStandardMaterial({
          color: '#cbd2d7',
          roughness: 0.42,
          metalness: 0.55,
        })
        object.material = material
        object.castShadow = true
        object.receiveShadow = true
      })
      robotRef.current = robot
      scene.add(robot)
    })

    const resize = () => {
      const width = host.clientWidth
      const height = host.clientHeight
      if (!width || !height) return
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()
    let animation = 0
    const draw = () => {
      controls.update()
      renderer.render(scene, camera)
      animation = requestAnimationFrame(draw)
    }
    draw()
    return () => {
      cancelAnimationFrame(animation)
      observer.disconnect()
      controls.dispose()
      renderer.dispose()
      renderer.domElement.remove()
      robotRef.current = null
    }
  }, [])

  useEffect(() => {
    const robot = robotRef.current
    if (!robot || !joints) return
    Object.entries(joints).forEach(([name, value]) => robot.setJointValue(name, value))
  }, [joints])

  return <div className="robot-viewport" ref={hostRef} data-testid="robot-viewport" />
}
