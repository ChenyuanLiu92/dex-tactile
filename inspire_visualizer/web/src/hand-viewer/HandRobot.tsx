import { createPortal } from '@react-three/fiber'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Box3, LoadingManager, Mesh, Vector3 } from 'three'
import URDFLoader, { type URDFRobot } from 'urdf-loader'

import type { ChannelValues, HandSide } from '../app/types'
import { showsTargetPose, type WorkspaceMode } from '../app/workspaceMode'
import { CoordinateFrame } from './CoordinateFrame'
import { ACTUATOR_REFERENCES, mapDeviceAngles } from './jointMapping'

const MODEL_CONFIG = {
  left: {
    url: '/models/left/left.urdf',
    packages: { urdf_left: '/models/left' },
  },
  right: {
    url: '/models/right/right.urdf',
    packages: { urdf_right: '/models/right' },
  },
} as const

function loadRobot(side: HandSide): Promise<URDFRobot> {
  const manager = new LoadingManager()
  const loader = new URDFLoader(manager)
  const config = MODEL_CONFIG[side]
  loader.packages = config.packages
  loader.parseCollision = false

  return new Promise((resolve, reject) => {
    let robot: URDFRobot | null = null
    let settled = false
    let geometryCheckStarted = false

    const finishWhenGeometryIsReady = (attempt = 0) => {
      if (settled) return
      if (robot && !new Box3().setFromObject(robot).isEmpty()) {
        settled = true
        resolve(robot)
        return
      }
      if (attempt >= 100) {
        settled = true
        reject(new Error(`${side} hand model contains no visible geometry`))
        return
      }
      window.setTimeout(() => finishWhenGeometryIsReady(attempt + 1), 50)
    }

    manager.onLoad = () => {
      if (geometryCheckStarted) return
      geometryCheckStarted = true
      window.setTimeout(finishWhenGeometryIsReady, 0)
    }
    manager.onError = (url) => {
      if (settled) return
      settled = true
      reject(new Error(`Unable to load model asset: ${url}`))
    }
    loader.load(
      config.url,
      (loaded) => {
        robot = loaded
      },
      undefined,
      reject,
    )
  })
}

function normalizeRobot(robot: URDFRobot, side: HandSide): void {
  if (side === 'right') {
    const baseLink = robot.links.base_link
    baseLink.removeFromParent()
    robot.add(baseLink)
  }
  robot.rotation.set(-Math.PI / 2, 0, 0)
  if (side === 'right') robot.rotateZ(Math.PI)
  robot.updateMatrixWorld(true)
  const bounds = new Box3().setFromObject(robot)
  if (bounds.isEmpty()) throw new Error(`${side} hand model contains no visible geometry`)
  const center = bounds.getCenter(new Vector3())
  robot.position.set(-center.x, -bounds.min.y, -center.z)

  if (side === 'left') {
    robot.joints.left_thumb_2_joint.ignoreLimits = true
    robot.joints.left_thumb_3_joint.ignoreLimits = true
  }

  robot.traverse((object) => {
    if (object instanceof Mesh) {
      object.castShadow = true
      object.receiveShadow = true
    }
  })
}

function styleGhost(robot: URDFRobot): void {
  robot.traverse((object) => {
    if (object instanceof Mesh) {
      const material = Array.isArray(object.material)
        ? object.material.map((item) => item.clone())
        : object.material.clone()
      const materials = Array.isArray(material) ? material : [material]
      for (const item of materials) {
        item.transparent = true
        item.opacity = 0.22
        item.depthWrite = false
        item.color.set('#d3913b')
      }
      object.material = material
      object.castShadow = false
    }
  })
}

function useRobot(side: HandSide) {
  const [robot, setRobot] = useState<URDFRobot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let disposed = false
    loadRobot(side)
      .then((loaded) => {
        if (disposed) return
        normalizeRobot(loaded, side)
        setRobot(loaded)
      })
      .catch((reason: unknown) => {
        if (!disposed) setError(reason instanceof Error ? reason.message : 'Unable to load hand model')
      })
    return () => {
      disposed = true
    }
  }, [side])

  return { robot, error }
}

interface HandRobotProps {
  side: HandSide
  actual: ChannelValues
  target: ChannelValues
  mode: WorkspaceMode
  positionX: number
  showBaseFrame: boolean
  showActuatorFrames: boolean
  onError: (message: string) => void
}

export function HandRobot({
  side,
  actual,
  target,
  mode,
  positionX,
  showBaseFrame,
  showActuatorFrames,
  onError,
}: HandRobotProps) {
  const { robot, error } = useRobot(side)
  const ghost = useMemo(() => {
    if (!robot) return null
    const clone = robot.clone(true) as URDFRobot
    styleGhost(clone)
    return clone
  }, [robot])
  const targetDiffers = target.some((value, index) => Math.abs(value - actual[index]) > 2)

  useEffect(() => {
    if (error) onError(error)
  }, [error, onError])

  useEffect(() => {
    robot?.setJointValues(mapDeviceAngles(side, actual))
  }, [actual, robot, side])

  useEffect(() => {
    ghost?.setJointValues(mapDeviceAngles(side, target))
  }, [ghost, side, target])

  if (!robot) return null

  return (
    <group position={[positionX, 0, 0]}>
      <primitive object={robot} />
      {showsTargetPose(mode) && ghost && targetDiffers ? <primitive object={ghost} /> : null}
      {showBaseFrame && robot.links.base_link
        ? createPortal(
            <CoordinateFrame
              label={`${side === 'left' ? 'L' : 'R'} BASE / MOUNT`}
              size={0.042}
              kind="base"
            />,
            robot.links.base_link,
          )
        : null}
      {showActuatorFrames
        ? ACTUATOR_REFERENCES[side].map((reference) => {
            const joint = robot.joints[reference.joint]
            if (!joint) return null
            return (
              <Fragment key={reference.channel}>
                {createPortal(
                  <CoordinateFrame
                    label={`${side === 'left' ? 'L' : 'R'} ${reference.channel}`}
                    size={0.019}
                    kind="actuator"
                  />,
                  joint,
                )}
              </Fragment>
            )
          })
        : null}
    </group>
  )
}
