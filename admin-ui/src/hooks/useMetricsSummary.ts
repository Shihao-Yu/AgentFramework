import { useState, useEffect, useCallback } from 'react'
import { apiRequest } from '@/lib/api'

interface MetricsSummaryResponse {
  total_items: number
  published_items: number
  draft_items: number
  archived_items: number
  total_hits: number
  total_sessions: number
  avg_daily_sessions: number
  never_accessed_count: number
}

interface MetricsSummary {
  totalItems: number
  publishedItems: number
  draftItems: number
  archivedItems: number
  totalHits: number
  totalSessions: number
  avgDailySessions: number
  neverAccessedCount: number
}

interface UseMetricsSummaryOptions {
  nodeTypes?: string[]
  days?: number
}

export function useMetricsSummary(options: UseMetricsSummaryOptions = {}) {
  const { nodeTypes, days = 7 } = options
  const [summary, setSummary] = useState<MetricsSummary>({
    totalItems: 0,
    publishedItems: 0,
    draftItems: 0,
    archivedItems: 0,
    totalHits: 0,
    totalSessions: 0,
    avgDailySessions: 0,
    neverAccessedCount: 0,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSummary = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const params: Record<string, string | string[]> = { days: String(days) }
      if (nodeTypes && nodeTypes.length > 0) {
        params.node_types = nodeTypes
      }

      const res = await apiRequest<MetricsSummaryResponse>('/api/metrics/summary', { params })

      setSummary({
        totalItems: res.total_items,
        publishedItems: res.published_items,
        draftItems: res.draft_items,
        archivedItems: res.archived_items,
        totalHits: res.total_hits,
        totalSessions: res.total_sessions,
        avgDailySessions: res.avg_daily_sessions,
        neverAccessedCount: res.never_accessed_count,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch metrics summary'
      setError(message)
      console.error('Failed to fetch metrics summary:', err)
    } finally {
      setIsLoading(false)
    }
  }, [nodeTypes, days])

  useEffect(() => {
    fetchSummary()
  }, [fetchSummary])

  return {
    summary,
    isLoading,
    error,
    refetch: fetchSummary,
  }
}
