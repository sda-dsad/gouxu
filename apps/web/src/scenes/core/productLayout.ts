import type {Product} from '../../domain/types'

export type ProductAxisMode = 'auto' | 'full'
export type ProductMetric = 'click' | 'purchase_feedback'
export interface ProductScale { min: number; max: number; ticks: number[]; mode: ProductAxisMode }

// Presentation only: keep a zero origin and linear coordinates in both renderers.
export function productScale(products: Product[], metric: ProductMetric, mode: ProductAxisMode): ProductScale {
  const values = products.filter(p => p.E > 0).map(p => metric === 'click' ? p.click_rate : p.purchase_rate)
    .filter((v): v is number => v != null && Number.isFinite(v) && v >= 0 && v <= 1)
  let max = 1
  if (mode === 'auto') {
    const target = Math.max(.01, Math.max(0, ...values) * 1.12)
    const magnitude = 10 ** Math.floor(Math.log10(target))
    max = Math.min(1, ([1, 2, 3, 4, 5, 6, 8, 10].find(n => n * magnitude >= target - 1e-12) ?? 10) * magnitude)
  }
  return {min: 0, max, ticks: Array.from({length: 6}, (_, i) => max * i / 5), mode}
}

export function axisPercent(value: number): string {
  return Number((value * 100).toFixed(2)).toString() + '%'
}

// Fit the actual displayed exposure counts, retaining outliers and integer ticks.
export function exposureScale(products: Product[], snapshotMax: number, mode: ProductAxisMode): ProductScale {
  const values = products.map(p => p.E).filter(v => Number.isSafeInteger(v) && v > 0)
  const fullMax = Math.max(1, Number.isSafeInteger(snapshotMax) && snapshotMax > 0 ? snapshotMax : 1, ...values)
  if (mode === 'full' || !values.length) {
    return {min: 0, max: fullMax, ticks: [...new Set(Array.from({length: 6}, (_, i) => Math.round(fullMax * i / 5)))], mode}
  }
  const low = Math.min(...values), high = Math.max(...values), padding = Math.max(1, (high - low) * .1)
  const desiredStep = Math.max(1, (high - low + 2 * padding) / 5)
  const magnitude = 10 ** Math.floor(Math.log10(desiredStep))
  const step = ([1, 2, 5, 10].find(n => n * magnitude >= desiredStep) ?? 10) * magnitude
  const min = Math.max(0, Math.floor((low - padding) / step) * step)
  const max = Math.max(min + step, Math.ceil((high + padding) / step) * step)
  return {min, max, ticks: Array.from({length: Math.round((max - min) / step) + 1}, (_, i) => min + i * step), mode}
}

export function scalePosition(value: number, scale: ProductScale): number {
  return (value - scale.min) / (scale.max - scale.min)
}

export interface ProjectedMarker {id: string; x: number; y: number; members: string[]}
export interface MarkerCluster<T extends ProjectedMarker> {anchor: T; members: string[]}

// Cluster only the screen-space hit labels. Every GPU/SVG point stays at its exact data coordinate.
// The representative is an existing point, never a jittered or averaged statistic.
export function markerClusters<T extends ProjectedMarker>(points: T[], selected: string | null, gap = 28): MarkerCluster<T>[] {
  const seen = new Set<number>(), clusters: MarkerCluster<T>[] = []
  for (let start = 0; start < points.length; start++) {
    if (seen.has(start)) continue
    seen.add(start)
    const indices = [start]
    for (let cursor = 0; cursor < indices.length; cursor++) {
      const p = points[indices[cursor]!]!
      for (let i = 0; i < points.length; i++) {
        if (!seen.has(i) && Math.hypot(p.x - points[i]!.x, p.y - points[i]!.y) < gap) {
          seen.add(i); indices.push(i)
        }
      }
    }
    const group = indices.map(i => points[i]!), anchor = group.find(p => selected != null && p.members.includes(selected)) ?? group[0]!
    clusters.push({anchor, members: [...new Set(group.flatMap(p => p.members))]})
  }
  return clusters
}
