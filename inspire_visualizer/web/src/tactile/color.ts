type Rgba = [number, number, number, number]

const STOPS: Array<[number, Rgba]> = [
  [0, [8, 16, 20, 255]],
  [0.2, [15, 62, 74, 255]],
  [0.45, [25, 141, 155, 255]],
  [0.68, [198, 137, 47, 255]],
  [0.86, [238, 104, 52, 255]],
  [1, [255, 250, 225, 255]],
]

export function normalizedTactileValue(
  raw: number,
  baseline: number,
  threshold: number,
  scale: number,
): number {
  return Math.min(1, Math.max(0, raw - baseline - threshold) / Math.max(1, scale))
}

export function heatColor(value: number): Rgba {
  const normalized = Math.min(1, Math.max(0, value))
  for (let index = 1; index < STOPS.length; index += 1) {
    const [endAt, end] = STOPS[index]
    const [startAt, start] = STOPS[index - 1]
    if (normalized <= endAt) {
      const amount = (normalized - startAt) / (endAt - startAt)
      return start.map((channel, channelIndex) =>
        Math.round(channel + (end[channelIndex] - channel) * amount),
      ) as Rgba
    }
  }
  return STOPS[STOPS.length - 1][1]
}
