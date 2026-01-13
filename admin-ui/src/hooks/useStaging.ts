import { useState, useCallback, useMemo, useEffect } from 'react'
import { apiRequest, shouldUseMock, delay } from '@/lib/api'
import { mockStagingItems, mockKnowledgeItems } from '@/data/mock-data'
import type { StagingKnowledgeItem, LegacyKnowledgeItem } from '@/types/knowledge'

interface StagingListResponse {
  items: StagingKnowledgeItem[]
  total: number
  page: number
  limit: number
}

interface StagingReviewResponse {
  success: boolean
  staging_id: number
  created_item_id?: number
  message: string
}

export function useStaging() {
  const [items, setItems] = useState<StagingKnowledgeItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pendingItems = useMemo(() => {
    return items.filter((item) => item.status === 'pending')
  }, [items])

  const countByAction = useMemo(() => {
    return {
      new: pendingItems.filter((i) => i.action === 'new').length,
      merge: pendingItems.filter((i) => i.action === 'merge').length,
      add_variant: pendingItems.filter((i) => i.action === 'add_variant').length,
    }
  }, [pendingItems])

  const fetchItems = useCallback(async () => {
    if (shouldUseMock()) {
      setItems(mockStagingItems)
      return
    }

    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<StagingListResponse>('/api/staging', {
        params: { status: 'pending', limit: 100 },
      })
      setItems(response.items)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch staging items'
      setError(message)
      console.error('Failed to fetch staging items:', err)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  const getMergeTarget = useCallback((stagingItem: StagingKnowledgeItem): LegacyKnowledgeItem | undefined => {
    if (!stagingItem.merge_with_id) return undefined
    return mockKnowledgeItems.find((i) => i.id === stagingItem.merge_with_id)
  }, [])

  const approveItem = useCallback(async (
    id: number,
    options?: {
      editedContent?: Partial<StagingKnowledgeItem>
    }
  ): Promise<void> => {
    if (shouldUseMock()) {
      await delay(500)
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            return {
              ...item,
              ...(options?.editedContent || {}),
              status: 'approved',
              reviewed_by: 'current-user',
              reviewed_at: new Date().toISOString(),
            }
          }
          return item
        })
      )
      return
    }

    setIsLoading(true)
    setError(null)
    
    try {
      await apiRequest<StagingReviewResponse>(`/api/staging/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ edits: options?.editedContent }),
      })
      
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to approve item'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const rejectItem = useCallback(async (id: number, reason?: string): Promise<void> => {
    if (shouldUseMock()) {
      await delay(300)
      setItems((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            return {
              ...item,
              status: 'rejected',
              reviewed_by: 'current-user',
              reviewed_at: new Date().toISOString(),
              review_notes: reason,
            }
          }
          return item
        })
      )
      return
    }

    setIsLoading(true)
    setError(null)
    
    try {
      await apiRequest<StagingReviewResponse>(`/api/staging/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      })
      
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reject item'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const editAndApprove = useCallback(async (
    id: number,
    editedData: {
      title?: string
      question?: string
      answer?: string
      tags?: string[]
    }
  ): Promise<void> => {
    if (shouldUseMock()) {
      await delay(500)
      setItems((prev) =>
        prev.map((item): StagingKnowledgeItem => {
          if (item.id === id) {
            const currentContent = item.content as Record<string, unknown>
            const newContent = {
              ...currentContent,
              ...(editedData.question ? { question: editedData.question } : {}),
              ...(editedData.answer ? { answer: editedData.answer } : {}),
            }

            return {
              ...item,
              title: editedData.title || item.title,
              content: newContent,
              tags: editedData.tags || item.tags,
              status: 'approved' as const,
              reviewed_by: 'current-user',
              reviewed_at: new Date().toISOString(),
            }
          }
          return item
        })
      )
      return
    }

    setIsLoading(true)
    setError(null)
    
    try {
      const edits: Record<string, unknown> = {}
      if (editedData.title) edits.title = editedData.title
      if (editedData.tags) edits.tags = editedData.tags
      if (editedData.question || editedData.answer) {
        edits.content = {}
        if (editedData.question) (edits.content as Record<string, unknown>).question = editedData.question
        if (editedData.answer) (edits.content as Record<string, unknown>).answer = editedData.answer
      }

      await apiRequest<StagingReviewResponse>(`/api/staging/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ edits }),
      })
      
      setItems((prev) => prev.filter((item) => item.id !== id))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to edit and approve item'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const getItem = useCallback((id: number): StagingKnowledgeItem | undefined => {
    return items.find((item) => item.id === id)
  }, [items])

  return {
    items,
    pendingItems,
    countByAction,
    isLoading,
    error,
    getMergeTarget,
    approveItem,
    rejectItem,
    editAndApprove,
    getItem,
    refetch: fetchItems,
  }
}
