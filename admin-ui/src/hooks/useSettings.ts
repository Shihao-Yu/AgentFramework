import { useState, useCallback, useEffect } from 'react'
import { apiRequest } from '@/lib/api'

export interface SearchSettings {
  bm25_weight: number
  vector_weight: number
  default_limit: number
}

export interface PipelineSettings {
  similarity_skip_threshold: number
  similarity_variant_threshold: number
  similarity_merge_threshold: number
  confidence_threshold: number
  min_body_length: number
  min_closure_notes_length: number
}

export interface MaintenanceSettings {
  version_retention_days: number
  hit_retention_days: number
}

export interface Settings {
  search: SearchSettings
  pipeline: PipelineSettings
  maintenance: MaintenanceSettings
}

export function useSettings() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchSettings = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await apiRequest<Settings>('/api/settings')
      setSettings(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch settings'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const updateSettings = useCallback(async (data: Partial<Settings>): Promise<void> => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await apiRequest<Settings>('/api/settings', {
        method: 'PATCH',
        body: JSON.stringify(data),
      })
      setSettings(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update settings'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    settings,
    isLoading,
    error,
    updateSettings,
    refetch: fetchSettings,
  }
}
