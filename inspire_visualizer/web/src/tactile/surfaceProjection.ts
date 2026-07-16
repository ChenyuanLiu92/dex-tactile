import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  DoubleSide,
  Material,
  Matrix4,
  Mesh,
  Object3D,
  Raycaster,
  Vector3,
} from 'three'

import type { SurfaceAxis, TactilePatchLayout } from './layout'
import type { BilinearTransform } from './spatialCalibration'
import { applyBilinearTransform } from './spatialCalibration'

const DEFAULT_SURFACE_OFFSET = 0.00015

export interface ProjectedPoint {
  point: Vector3
  normal: Vector3
}

interface ProjectedSurface {
  geometry: BufferGeometry
  projectedVertices: number
  sampledVertices: number
  coverage: number
  projectedMask: boolean[]
  interpolatedVertices: number
}

interface LinkObject extends Object3D {
  isURDFLink?: boolean
}

function ownedMeshes(root: Object3D): Mesh[] {
  const result: Mesh[] = []
  const visit = (object: LinkObject) => {
    if (object !== root && object.isURDFLink) return
    if (object instanceof Mesh) result.push(object)
    for (const child of object.children) visit(child as LinkObject)
  }
  visit(root as LinkObject)
  return result
}

export function localOwnedMeshBounds(root: Object3D): Box3 {
  const meshes = ownedMeshes(root)
  root.updateWorldMatrix(true, true)
  const worldToRoot = root.matrixWorld.clone().invert()
  const bounds = new Box3()
  const point = new Vector3()
  for (const mesh of meshes) {
    const position = mesh.geometry.getAttribute('position')
    if (!position) continue
    const meshToRoot = new Matrix4().multiplyMatrices(worldToRoot, mesh.matrixWorld)
    for (let index = 0; index < position.count; index += 1) {
      point.fromBufferAttribute(position, index).applyMatrix4(meshToRoot)
      bounds.expandByPoint(point)
    }
  }
  return bounds
}

function withDoubleSidedMaterials<T>(meshes: Mesh[], run: () => T): T {
  const originals = new Map<Material, Material['side']>()
  for (const mesh of meshes) {
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
    for (const material of materials) {
      if (!originals.has(material)) originals.set(material, material.side)
      material.side = DoubleSide
    }
  }
  try {
    return run()
  } finally {
    for (const [material, side] of originals) material.side = side
  }
}

function localHitNormal(root: Object3D, hitPoint: Vector3, hitObject: Object3D, faceNormal: Vector3): Vector3 {
  const worldNormal = faceNormal.clone().transformDirection(hitObject.matrixWorld)
  const localPoint = root.worldToLocal(hitPoint.clone())
  const localNormalEnd = root.worldToLocal(hitPoint.clone().add(worldNormal))
  return localNormalEnd.sub(localPoint).normalize()
}

function axisValue(vector: Vector3, axis: SurfaceAxis): number {
  return axis === 0 ? vector.x : axis === 1 ? vector.y : vector.z
}

function setAxisValue(vector: Vector3, axis: SurfaceAxis, value: number): void {
  if (axis === 0) vector.x = value
  else if (axis === 1) vector.y = value
  else vector.z = value
}

function normalizedAxisValue(bounds: Box3, axis: SurfaceAxis, value: number): number {
  const minimum = axisValue(bounds.min, axis)
  return minimum + (axisValue(bounds.max, axis) - minimum) * value
}

function axisDirection(axis: SurfaceAxis, sign: number): Vector3 {
  const direction = new Vector3()
  setAxisValue(direction, axis, sign)
  return direction
}

export function projectPointToSurface(
  link: Object3D,
  patch: TactilePatchLayout,
  uv: [number, number],
  surfaceOffset = DEFAULT_SURFACE_OFFSET,
): ProjectedPoint | null {
  const meshes = ownedMeshes(link)
  const bounds = localOwnedMeshBounds(link)
  if (bounds.isEmpty()) return null
  const { surface } = patch
  const normalMinimum = axisValue(bounds.min, surface.normalAxis)
  const normalMaximum = axisValue(bounds.max, surface.normalAxis)
  const outsideSign = surface.normalSide === 'min' ? -1 : 1
  const sample = new Vector3()
  setAxisValue(sample, surface.uAxis, normalizedAxisValue(bounds, surface.uAxis, uv[0]))
  setAxisValue(sample, surface.vAxis, normalizedAxisValue(bounds, surface.vAxis, uv[1]))
  setAxisValue(sample, surface.normalAxis, surface.normalSide === 'min' ? normalMinimum - surface.margin : normalMaximum + surface.margin)
  const direction = axisDirection(surface.normalAxis, -outsideSign)
  const raycaster = new Raycaster()
  const worldScale = link.getWorldScale(new Vector3())
  raycaster.far = (normalMaximum - normalMinimum + surface.margin * 2) * Math.max(Math.abs(worldScale.x), Math.abs(worldScale.y), Math.abs(worldScale.z))
  return withDoubleSidedMaterials(meshes, () => {
    const worldOrigin = link.localToWorld(sample.clone())
    raycaster.set(worldOrigin, direction.clone().transformDirection(link.matrixWorld))
    const hit = raycaster.intersectObjects(meshes, false)[0]
    if (!hit) return null
    const point = link.worldToLocal(hit.point.clone())
    const normal = hit.face ? localHitNormal(link, hit.point, hit.object, hit.face.normal) : direction.clone().negate()
    if (normal.dot(direction) > 0) normal.negate()
    return { point: point.addScaledVector(normal, surfaceOffset), normal }
  })
}

function bridgeInteriorGaps(
  projected: Array<Vector3 | null>,
  normals: Array<Vector3 | null>,
  rows: number,
  columns: number,
): number {
  const sourcePoints = projected.slice()
  const sourceNormals = normals.slice()
  const stride = columns + 1
  const maxDistance = 2
  let bridged = 0

  const find = (row: number, column: number, rowStep: number, columnStep: number) => {
    for (let distance = 1; distance <= maxDistance; distance += 1) {
      const candidateRow = row + rowStep * distance
      const candidateColumn = column + columnStep * distance
      if (candidateRow < 0 || candidateRow > rows || candidateColumn < 0 || candidateColumn > columns) {
        return null
      }
      const index = candidateRow * stride + candidateColumn
      if (sourcePoints[index]) return { index, distance }
    }
    return null
  }

  const interpolatePair = (
    index: number,
    first: { index: number; distance: number },
    second: { index: number; distance: number },
  ) => {
    const mix = first.distance / (first.distance + second.distance)
    projected[index] = (sourcePoints[first.index] as Vector3)
      .clone()
      .lerp(sourcePoints[second.index] as Vector3, mix)
    normals[index] = (sourceNormals[first.index] as Vector3)
      .clone()
      .lerp(sourceNormals[second.index] as Vector3, mix)
      .normalize()
    bridged += 1
  }

  for (let row = 0; row <= rows; row += 1) {
    for (let column = 0; column <= columns; column += 1) {
      const index = row * stride + column
      if (sourcePoints[index]) continue
      const left = find(row, column, 0, -1)
      const right = find(row, column, 0, 1)
      if (left && right) {
        interpolatePair(index, left, right)
        continue
      }
      const above = find(row, column, -1, 0)
      const below = find(row, column, 1, 0)
      if (above && below) interpolatePair(index, above, below)
    }
  }
  return bridged
}

export function projectPatchToSurface(
  link: Object3D,
  patch: TactilePatchLayout,
  rows: number,
  columns: number,
  calibration?: BilinearTransform,
  surfaceOffset = DEFAULT_SURFACE_OFFSET,
): ProjectedSurface {
  const meshes = ownedMeshes(link)
  const bounds = localOwnedMeshBounds(link)
  const sampledVertices = (rows + 1) * (columns + 1)
  if (bounds.isEmpty()) {
    return emptyProjectedSurface(sampledVertices)
  }

  const { surface } = patch
  const normalMinimum = axisValue(bounds.min, surface.normalAxis)
  const normalMaximum = axisValue(bounds.max, surface.normalAxis)
  const outsideSign = surface.normalSide === 'min' ? -1 : 1
  const normalCoordinate = surface.normalSide === 'min'
    ? normalMinimum - surface.margin
    : normalMaximum + surface.margin
  const localDirection = axisDirection(surface.normalAxis, -outsideSign)
  const projectionDistance = normalMaximum - normalMinimum + surface.margin * 2
  const worldScale = link.getWorldScale(new Vector3())
  const distanceScale = Math.max(Math.abs(worldScale.x), Math.abs(worldScale.y), Math.abs(worldScale.z))
  const raycaster = new Raycaster()
  raycaster.far = projectionDistance * distanceScale

  const samples: Vector3[] = []
  const projected: Array<Vector3 | null> = []
  const normals: Array<Vector3 | null> = []

  const cast = (origin: Vector3, direction: Vector3) => {
    const worldOrigin = link.localToWorld(origin.clone())
    const worldRayDirection = direction.clone().transformDirection(link.matrixWorld)
    raycaster.set(worldOrigin, worldRayDirection)
    const hit = raycaster.intersectObjects(meshes, false)[0]
    if (!hit) return null
    const hitLocal = link.worldToLocal(hit.point.clone())
    const normal = hit.face
      ? localHitNormal(link, hit.point, hit.object, hit.face.normal)
      : direction.clone().negate()
    if (normal.dot(localDirection) > 0) normal.negate()
    return { point: hitLocal.addScaledVector(normal, surfaceOffset), normal }
  }

  withDoubleSidedMaterials(meshes, () => {
    for (let row = 0; row <= rows; row += 1) {
      const rowMix = rows === 0 ? 0 : row / rows
      for (let column = 0; column <= columns; column += 1) {
        const columnMix = columns === 0 ? 0 : column / columns
        const calibratedPoint = calibration ? applyBilinearTransform(calibration, row, column, rows + 1, columns + 1) : null
        const u = calibratedPoint?.[0] ?? (surface.uRange[0] + (surface.uRange[1] - surface.uRange[0]) * columnMix)
        const projectedV = calibratedPoint?.[1] ?? (surface.vRange[0] + (surface.vRange[1] - surface.vRange[0]) * rowMix)
        const sample = new Vector3()
        setAxisValue(sample, surface.uAxis, normalizedAxisValue(bounds, surface.uAxis, u))
        setAxisValue(sample, surface.vAxis, normalizedAxisValue(bounds, surface.vAxis, projectedV))
        setAxisValue(sample, surface.normalAxis, normalCoordinate)
        samples.push(sample)
        const hit = cast(sample, localDirection)
        projected.push(hit?.point ?? null)
        normals.push(hit?.normal ?? null)
      }
    }
  })

  const projectedVertices = projected.filter(Boolean).length
  const interpolatedVertices = bridgeInteriorGaps(projected, normals, rows, columns)
  const positions: number[] = []
  const normalValues: number[] = []
  const uvs: number[] = []
  for (let row = 0; row <= rows; row += 1) {
    for (let column = 0; column <= columns; column += 1) {
      const index = row * (columns + 1) + column
      const position = projected[index] ?? samples[index]
      const normal = normals[index] ?? localDirection.clone().negate()
      positions.push(position.x, position.y, position.z)
      normalValues.push(normal.x, normal.y, normal.z)
      uvs.push(column / columns, 1 - row / rows)
    }
  }

  const indices: number[] = []
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const topLeft = row * (columns + 1) + column
      const topRight = topLeft + 1
      const bottomLeft = (row + 1) * (columns + 1) + column
      const bottomRight = bottomLeft + 1
      if (![topLeft, topRight, bottomLeft, bottomRight].every((index) => projected[index])) continue
      indices.push(topLeft, bottomLeft, topRight, topRight, bottomLeft, bottomRight)
    }
  }

  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
  geometry.setAttribute('normal', new BufferAttribute(new Float32Array(normalValues), 3))
  geometry.setAttribute('uv', new BufferAttribute(new Float32Array(uvs), 2))
  geometry.setIndex(indices)
  geometry.computeBoundingBox()
  geometry.computeBoundingSphere()
  return {
    geometry,
    projectedVertices,
    sampledVertices,
    coverage: projectedVertices / sampledVertices,
    projectedMask: projected.map(Boolean),
    interpolatedVertices,
  }
}

function emptyProjectedSurface(sampledVertices: number): ProjectedSurface {
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(sampledVertices * 3), 3))
  geometry.setAttribute('normal', new BufferAttribute(new Float32Array(sampledVertices * 3), 3))
  geometry.setAttribute('uv', new BufferAttribute(new Float32Array(sampledVertices * 2), 2))
  geometry.setIndex([])
  return {
    geometry,
    projectedVertices: 0,
    sampledVertices,
    coverage: 0,
    projectedMask: Array.from({ length: sampledVertices }, () => false),
    interpolatedVertices: 0,
  }
}

export function projectedCellGeometry(
  source: BufferGeometry,
  row: number,
  column: number,
  columns: number,
  rowSpan = 1,
  columnSpan = 1,
): BufferGeometry {
  const stride = columns + 1
  const sourcePositions = source.getAttribute('position')
  const sourceNormals = source.getAttribute('normal')
  const positions: number[] = []
  const normals: number[] = []
  for (let localRow = 0; localRow <= rowSpan; localRow += 1) {
    for (let localColumn = 0; localColumn <= columnSpan; localColumn += 1) {
      const index = (row + localRow) * stride + column + localColumn
      positions.push(sourcePositions.getX(index), sourcePositions.getY(index), sourcePositions.getZ(index))
      normals.push(sourceNormals.getX(index), sourceNormals.getY(index), sourceNormals.getZ(index))
    }
  }
  const cellIndices: number[] = []
  for (let localRow = 0; localRow < rowSpan; localRow += 1) {
    for (let localColumn = 0; localColumn < columnSpan; localColumn += 1) {
      const topLeft = localRow * (columnSpan + 1) + localColumn
      const topRight = topLeft + 1
      const bottomLeft = (localRow + 1) * (columnSpan + 1) + localColumn
      const bottomRight = bottomLeft + 1
      cellIndices.push(topLeft, bottomLeft, topRight, topRight, bottomLeft, bottomRight)
    }
  }
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(positions), 3))
  geometry.setAttribute('normal', new BufferAttribute(new Float32Array(normals), 3))
  geometry.setIndex(cellIndices)
  return geometry
}
