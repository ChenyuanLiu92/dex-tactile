export type WorkspaceMode = 'motion' | 'tactile' | 'combined'

export function showsTargetPose(mode: WorkspaceMode): boolean {
  return mode === 'motion' || mode === 'combined'
}

export function showsTactile(mode: WorkspaceMode): boolean {
  return mode === 'tactile' || mode === 'combined'
}
