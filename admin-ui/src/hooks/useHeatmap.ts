import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { apiRequest } from '@/lib/api'

// ==================== Types ====================

export type HeatmapPeriod = '7d' | '30d' | '90d' | 'all'
export type HeatmapMetric = 'hits' | 'sessions'

export interface HeatmapNodeData {
  id: number
  total_hits: number
  unique_sessions: number
  avg_similarity: number | null
  last_hit_at: string | null
  heat_score: number // 0-1
}

export interface HeatmapStats {
  total_nodes: number
  nodes_with_hits: number
  total_hits: number
  max_hits: number
  min_hits: number
}

export interface HeatmapResponse {
  period: string
  metric: string
  generated_at: string
  stats: HeatmapStats
  nodes: HeatmapNodeData[]
}

export interface HeatmapTagData {
  tag: string
  node_count: number
  total_hits: number
  heat_score: number
}

export interface HeatmapTagsResponse {
  period: string
  tags: HeatmapTagData[]
}

export interface HeatmapTypeData {
  node_type: string
  node_count: number
  total_hits: number
  heat_score: number
}

export interface HeatmapTypesResponse {
  period: string
  types: HeatmapTypeData[]
}

// ==================== Hook Options ====================

export interface UseHeatmapOptions {
  period?: HeatmapPeriod
  metric?: HeatmapMetric
  nodeTypes?: string[]
  includeZero?: boolean
  enabled?: boolean
}

// ==================== Main Hook ====================

export function useHeatmap(options: UseHeatmapOptions = {}) {
  const {
    period = '7d',
    metric = 'hits',
    nodeTypes,
    includeZero = true,
    enabled = true,
  } = options

  const queryKey = ['heatmap', period, metric, nodeTypes, includeZero]

  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const params: Record<string, string | boolean> = {
        period,
        metric,
        include_zero: includeZero,
      }
      if (nodeTypes?.length) {
        params.node_types = nodeTypes.join(',')
      }
      return apiRequest<HeatmapResponse>('/api/metrics/heatmap', { params })
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  })

  // Create a Map for O(1) lookup by node id
  const heatmapMap = useMemo(() => {
    if (!query.data?.nodes) return new Map<number, HeatmapNodeData>()
    return new Map(query.data.nodes.map((n) => [n.id, n]))
  }, [query.data])

  // Helper to get heat data for a specific node
  const getNodeHeat = (nodeId: number): HeatmapNodeData | undefined => {
    return heatmapMap.get(nodeId)
  }

  // Helper to get heat score for a specific node (returns 0 if not found)
  const getHeatScore = (nodeId: number): number => {
    return heatmapMap.get(nodeId)?.heat_score ?? 0
  }

  return {
    // Data
    heatmapData: heatmapMap,
    nodes: query.data?.nodes ?? [],
    stats: query.data?.stats,
    period: query.data?.period,
    metric: query.data?.metric,
    generatedAt: query.data?.generated_at,

    // Helpers
    getNodeHeat,
    getHeatScore,

    // Query state
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  }
}

// ==================== Tags Hook ====================

export interface UseHeatmapTagsOptions {
  period?: HeatmapPeriod
  limit?: number
  enabled?: boolean
}

export function useHeatmapTags(options: UseHeatmapTagsOptions = {}) {
  const { period = '7d', limit = 20, enabled = true } = options

  const query = useQuery({
    queryKey: ['heatmap-tags', period, limit],
    queryFn: () =>
      apiRequest<HeatmapTagsResponse>('/api/metrics/heatmap/tags', {
        params: { period, limit },
      }),
    enabled,
    staleTime: 5 * 60 * 1000,
  })

  return {
    tags: query.data?.tags ?? [],
    period: query.data?.period,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  }
}

// ==================== Types Hook ====================

export interface UseHeatmapTypesOptions {
  period?: HeatmapPeriod
  enabled?: boolean
}

export function useHeatmapTypes(options: UseHeatmapTypesOptions = {}) {
  const { period = '7d', enabled = true } = options

  const query = useQuery({
    queryKey: ['heatmap-types', period],
    queryFn: () =>
      apiRequest<HeatmapTypesResponse>('/api/metrics/heatmap/types', {
        params: { period },
      }),
    enabled,
    staleTime: 5 * 60 * 1000,
  })

  return {
    types: query.data?.types ?? [],
    period: query.data?.period,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  }
}
