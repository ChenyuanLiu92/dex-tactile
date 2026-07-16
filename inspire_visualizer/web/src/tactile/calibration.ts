import type { TactileFrame } from '../app/types'

export type TactileBaseline = Record<string, number[]>

function median(values: number[]): number {
  const sorted = [...values].sort((left, right) => left - right)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? ((sorted[middle - 1] ?? 0) + (sorted[middle] ?? 0)) / 2 : (sorted[middle] ?? 0)
}

export function baselineFromFrames(frames: TactileFrame[]): TactileBaseline {
  const samples: Record<string, number[][]> = {}
  for (const frame of frames) {
    for (const region of frame.regions) {
      const regionSamples = (samples[region.id] ??= region.values.map(() => []))
      region.values.forEach((value, index) => regionSamples[index]?.push(value))
    }
  }
  return Object.fromEntries(
    Object.entries(samples).map(([regionId, taxels]) => [
      regionId,
      taxels.map(median),
    ]),
  )
}

export function noiseFromFrames(frames: TactileFrame[], baseline: TactileBaseline): TactileBaseline {
  const deviations: Record<string, number[][]> = {}
  for (const frame of frames) for (const region of frame.regions) {
    const taxels = (deviations[region.id] ??= region.values.map(() => []))
    region.values.forEach((value, index) => taxels[index]?.push(Math.abs(value - (baseline[region.id]?.[index] ?? value))))
  }
  return Object.fromEntries(Object.entries(deviations).map(([id, taxels]) => [id, taxels.map(median)]))
}
