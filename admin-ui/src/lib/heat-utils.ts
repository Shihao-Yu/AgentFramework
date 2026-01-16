/**
 * Heat color utilities for graph heatmap visualization.
 * 
 * Maps heat scores (0-1) to colors using a gradient from cold (blue) to hot (red).
 */

// ==================== Color Constants ====================

export const HEAT_COLORS = {
  never: {
    bg: '#f3f4f6',     // gray-100
    border: '#d1d5db', // gray-300
    text: '#9ca3af',   // gray-400
  },
  cold: {
    bg: '#dbeafe',     // blue-100
    border: '#93c5fd', // blue-300
    text: '#1e40af',   // blue-800
  },
  cool: {
    bg: '#dcfce7',     // green-100
    border: '#86efac', // green-300
    text: '#166534',   // green-800
  },
  warm: {
    bg: '#fef9c3',     // yellow-100
    border: '#fde047', // yellow-300
    text: '#854d0e',   // yellow-800
  },
  hot: {
    bg: '#ffedd5',     // orange-100
    border: '#fdba74', // orange-300
    text: '#9a3412',   // orange-800
  },
  fire: {
    bg: '#fee2e2',     // red-100
    border: '#fca5a5', // red-300
    text: '#991b1b',   // red-800
  },
} as const

export type HeatLevel = keyof typeof HEAT_COLORS

// ==================== Heat Level Calculation ====================

/**
 * Get the heat level category for a given score.
 * 
 * @param score Heat score from 0-1, or undefined for type view mode
 * @returns Heat level category
 */
export function getHeatLevel(score: number | undefined): HeatLevel {
  if (score === undefined || score === null) return 'never'
  if (score === 0) return 'never'
  if (score <= 0.2) return 'cold'
  if (score <= 0.4) return 'cool'
  if (score <= 0.6) return 'warm'
  if (score <= 0.8) return 'hot'
  return 'fire'
}

/**
 * Get colors for a given heat score.
 * 
 * @param score Heat score from 0-1
 * @returns Object with bg, border, and text colors
 */
export function getHeatColors(score: number | undefined) {
  const level = getHeatLevel(score)
  return HEAT_COLORS[level]
}

/**
 * Get the background color for a heat score.
 */
export function getHeatBgColor(score: number | undefined): string {
  return getHeatColors(score).bg
}

/**
 * Get the border color for a heat score.
 */
export function getHeatBorderColor(score: number | undefined): string {
  return getHeatColors(score).border
}

// ==================== Style Utilities ====================

export interface HeatStyleOptions {
  isNeverAccessed?: boolean
  showGlow?: boolean
}

/**
 * Get CSS styles for a node based on heat score.
 * 
 * @param score Heat score from 0-1
 * @param options Additional style options
 * @returns CSS style object
 */
export function getHeatNodeStyle(
  score: number | undefined,
  options: HeatStyleOptions = {}
): React.CSSProperties {
  const colors = getHeatColors(score)
  const level = getHeatLevel(score)
  const isNever = level === 'never'
  
  const style: React.CSSProperties = {
    backgroundColor: colors.bg,
    borderColor: colors.border,
  }
  
  // Fade never-accessed nodes
  if (isNever) {
    style.opacity = 0.5
    style.borderStyle = 'dashed'
  }
  
  // Add glow effect for hot nodes
  if (options.showGlow && (level === 'hot' || level === 'fire')) {
    style.boxShadow = `0 0 12px ${colors.border}`
  }
  
  return style
}

// ==================== Legend Data ====================

export interface HeatLegendItem {
  level: HeatLevel
  label: string
  description: string
  minScore: number
  maxScore: number
  colors: typeof HEAT_COLORS[HeatLevel]
}

/**
 * Get legend items for the heat scale.
 */
export function getHeatLegendItems(): HeatLegendItem[] {
  return [
    {
      level: 'never',
      label: 'Never',
      description: 'Never accessed',
      minScore: 0,
      maxScore: 0,
      colors: HEAT_COLORS.never,
    },
    {
      level: 'cold',
      label: 'Cold',
      description: '1-20%',
      minScore: 0.01,
      maxScore: 0.2,
      colors: HEAT_COLORS.cold,
    },
    {
      level: 'cool',
      label: 'Cool',
      description: '21-40%',
      minScore: 0.21,
      maxScore: 0.4,
      colors: HEAT_COLORS.cool,
    },
    {
      level: 'warm',
      label: 'Warm',
      description: '41-60%',
      minScore: 0.41,
      maxScore: 0.6,
      colors: HEAT_COLORS.warm,
    },
    {
      level: 'hot',
      label: 'Hot',
      description: '61-80%',
      minScore: 0.61,
      maxScore: 0.8,
      colors: HEAT_COLORS.hot,
    },
    {
      level: 'fire',
      label: 'Fire',
      description: '81-100%',
      minScore: 0.81,
      maxScore: 1.0,
      colors: HEAT_COLORS.fire,
    },
  ]
}

// ==================== Formatting ====================

/**
 * Format a heat score as a percentage string.
 */
export function formatHeatPercent(score: number | undefined): string {
  if (score === undefined || score === null) return '-'
  return `${Math.round(score * 100)}%`
}

/**
 * Format hits count with K/M suffix for large numbers.
 */
export function formatHitsCount(hits: number): string {
  if (hits >= 1_000_000) {
    return `${(hits / 1_000_000).toFixed(1)}M`
  }
  if (hits >= 1_000) {
    return `${(hits / 1_000).toFixed(1)}K`
  }
  return hits.toString()
}
