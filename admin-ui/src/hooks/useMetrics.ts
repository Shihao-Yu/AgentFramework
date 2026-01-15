import { useState, useMemo, useEffect, useCallback } from 'react'
import { apiRequest } from '@/lib/api'
import type { KnowledgeHitStats, DailyHitStats } from '@/types/knowledge'

interface MetricsSummaryResponse {
  total_items: number
  published_items: number
  draft_items: number
  archived_items: number
  total_hits: number
  total_sessions: number
  avg_daily_hits: number
  avg_daily_sessions: number
  never_accessed_count: number
}

interface TopItemsResponse {
  items: KnowledgeHitStats[]
}

interface DailyTrendResponse {
  days: Array<{
    date: string
    total_hits: number
    unique_sessions: number
  }>
}

interface TagStatsResponse {
  tags: Array<{
    tag: string
    item_count: number
    total_hits: number
  }>
}

export function useMetrics() {
  const [hitStats, setHitStats] = useState<KnowledgeHitStats[]>([])
  const [dailyStats, setDailyStats] = useState<DailyHitStats[]>([])
  const [summary, setSummary] = useState({
    totalItems: 0,
    publishedItems: 0,
    draftItems: 0,
    totalHits: 0,
    totalSessions: 0,
    avgDailyHits: 0,
    avgDailySessions: 0,
    neverAccessedCount: 0,
  })
  const [tagCloud, setTagCloud] = useState<Array<{ tag: string; count: number }>>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const [summaryRes, topItemsRes, trendRes, tagsRes] = await Promise.all([
        apiRequest<MetricsSummaryResponse>('/api/metrics/summary', { params: { days: 7 } }),
        apiRequest<TopItemsResponse>('/api/metrics/top-items', { params: { limit: 10, days: 7 } }),
        apiRequest<DailyTrendResponse>('/api/metrics/daily-trend', { params: { days: 7 } }),
        apiRequest<TagStatsResponse>('/api/metrics/tags', { params: { limit: 20 } }),
      ])

      setSummary({
        totalItems: summaryRes.total_items,
        publishedItems: summaryRes.published_items,
        draftItems: summaryRes.draft_items,
        totalHits: summaryRes.total_hits,
        totalSessions: summaryRes.total_sessions,
        avgDailyHits: summaryRes.avg_daily_hits,
        avgDailySessions: summaryRes.avg_daily_sessions,
        neverAccessedCount: summaryRes.never_accessed_count,
      })

      setHitStats(topItemsRes.items)

      setDailyStats(trendRes.days.map(day => ({
        date: day.date,
        total_hits: day.total_hits,
        unique_sessions: day.unique_sessions,
        by_type: { faq: 0, playbook: 0, example: 0, schema: 0, permission: 0 },
      })))

      setTagCloud(tagsRes.tags.map(t => ({ tag: t.tag, count: t.item_count })))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch metrics'
      setError(message)
      console.error('Failed to fetch metrics:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMetrics()
  }, [fetchMetrics])

  const topItemsByHits = useMemo(() => {
    return [...hitStats].sort((a, b) => b.total_hits - a.total_hits).slice(0, 10)
  }, [hitStats])

  const typeDistribution = useMemo(() => {
    const types: Record<string, number> = {}
    for (const stat of hitStats) {
      const type = stat.knowledge_type
      types[type] = (types[type] || 0) + 1
    }
    return Object.entries(types)
      .map(([type, count]) => ({ type, count }))
      .filter(t => t.count > 0)
  }, [hitStats])

  const dailyTrend = useMemo(() => {
    return dailyStats.map((day) => ({
      date: day.date,
      hits: day.total_hits,
      sessions: day.unique_sessions,
    }))
  }, [dailyStats])

  return {
    summary,
    topItemsByHits,
    typeDistribution,
    tagCloud,
    dailyTrend,
    dailyStats,
    hitStats,
    isLoading,
    error,
    refetch: fetchMetrics,
  }
}
