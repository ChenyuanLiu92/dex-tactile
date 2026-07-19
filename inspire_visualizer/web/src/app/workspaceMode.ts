export type WorkspaceMode = 'motion' | 'tactile' | 'combined'

export function showsTargetPose(mode: WorkspaceMode): boolean {
  return mode === 'motion' || mode === 'combined'
}
