import { useState, useCallback } from 'react'
import { apiRequest } from '@/lib/api'

export interface ContentItem {
  text: string
  node_types: string[]
}

export interface OnboardRequest {
  items: ContentItem[]
  tenant_id: string
  source_tag: string
}

export interface OnboardResponse {
  created: number
  staging_ids: number[]
}

export function useOnboarding() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onboard = useCallback(async (request: OnboardRequest): Promise<OnboardResponse> => {
    setIsLoading(true)
    setError(null)

    try {
      const response = await apiRequest<OnboardResponse>('/api/onboard', {
        method: 'POST',
        body: JSON.stringify(request),
      })
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to onboard content'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    onboard,
    isLoading,
    error,
  }
}
