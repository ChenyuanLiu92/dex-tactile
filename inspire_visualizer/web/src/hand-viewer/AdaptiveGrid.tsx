import { Grid } from '@react-three/drei'
import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useRef, useState } from 'react'
import { Vector3 } from 'three'

export type GridLevelName = 'coarse' | 'standard' | 'fine' | 'micro'

export interface GridLevel {
  name: GridLevelName
  cellSize: number
  sectionSize: number
}

const GRID_LEVELS: Record<GridLevelName, GridLevel> = {
  coarse: { name: 'coarse', cellSize: 0.02, sectionSize: 0.1 },
  standard: { name: 'standard', cellSize: 0.01, sectionSize: 0.05 },
  fine: { name: 'fine', cellSize: 0.005, sectionSize: 0.025 },
  micro: { name: 'micro', cellSize: 0.0025, sectionSize: 0.0125 },
}

const GRID_TARGET = new Vector3(0, 0.1, 0)

export function gridLevelForDistance(distance: number): GridLevel {
  if (distance > 0.85) return GRID_LEVELS.coarse
  if (distance > 0.42) return GRID_LEVELS.standard
  if (distance > 0.24) return GRID_LEVELS.fine
  return GRID_LEVELS.micro
}

interface AdaptiveGridProps {
  onLevelChange?: (level: GridLevelName) => void
}

export function AdaptiveGrid({ onLevelChange }: AdaptiveGridProps) {
  const camera = useThree((state) => state.camera)
  const initialLevel = gridLevelForDistance(camera.position.distanceTo(GRID_TARGET))
  const levelRef = useRef(initialLevel)
  const [level, setLevel] = useState(initialLevel)

  useEffect(() => onLevelChange?.(level.name), [level.name, onLevelChange])

  useFrame(({ camera: activeCamera }) => {
    const nextLevel = gridLevelForDistance(activeCamera.position.distanceTo(GRID_TARGET))
    if (nextLevel.name === levelRef.current.name) return
    levelRef.current = nextLevel
    setLevel(nextLevel)
  })

  return (
    <Grid
      position={[0, -0.002, 0]}
      args={[1, 1]}
      cellSize={level.cellSize}
      cellThickness={0.62}
      cellColor="#354044"
      sectionSize={level.sectionSize}
      sectionThickness={1.2}
      sectionColor="#5d7078"
      fadeDistance={1.25}
      fadeStrength={1.25}
      infiniteGrid
    />
  )
}
