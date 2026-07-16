import { Color, Material, Mesh, Object3D } from 'three'

interface UrdfVisualObject extends Object3D {
  isURDFVisual?: boolean
}

function belongsToUrdfVisual(object: Object3D, root: Object3D): boolean {
  let current = object.parent as UrdfVisualObject | null
  while (current) {
    if (current.isURDFVisual) return true
    if (current === root) return false
    current = current.parent as UrdfVisualObject | null
  }
  return false
}

export function tintUrdfVisuals(root: Object3D, color: string): () => void {
  const originals = new Map<Material & { color?: Color }, Color>()
  root.traverse((object) => {
    if (!(object instanceof Mesh) || !belongsToUrdfVisual(object, root)) return
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    for (const material of materials) {
      const colored = material as Material & { color?: Color }
      if (!colored.color || originals.has(colored)) continue
      originals.set(colored, colored.color.clone())
      colored.color.set(color)
    }
  })
  return () => {
    for (const [material, original] of originals) material.color?.copy(original)
  }
}
