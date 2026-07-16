import type { TactileFrame } from '../app/types'

export interface RegionSummary {
  mean: number
  peak: number
  active: number
  total: number
}

export interface TactileHistorySample {
  capturedAt: number
  sequence: number
  regions: Record<string, RegionSummary>
}

export function summarizeFrame(frame: TactileFrame, threshold: number): TactileHistorySample {
  const regions: Record<string, RegionSummary> = {}
  for (const region of frame.regions) {
    const total = region.values.length
    const sum = region.values.reduce((current, value) => current + value, 0)
    regions[region.id] = {
      mean: total === 0 ? 0 : sum / total,
      peak: total === 0 ? 0 : Math.max(...region.values),
      active: region.values.filter((value) => value > threshold).length,
      total,
    }
  }
  return { capturedAt: frame.captured_at, sequence: frame.sequence, regions }
}

export function appendHistory(
  history: TactileHistorySample[],
  frame: TactileFrame,
  threshold: number,
): TactileHistorySample[] {
  const sample = summarizeFrame(frame, threshold)
  const cutoff = sample.capturedAt - 10
  return [...history.filter((entry) => entry.capturedAt >= cutoff), sample]
}
