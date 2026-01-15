import { useState, useCallback, useMemo, useEffect } from 'react'
import { apiRequest, delay } from '@/lib/api'
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

interface MergeTargetResponse {
  id: number
  title: string
  content: Record<string, unknown>
  tags: string[]
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
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<StagingListResponse>('/api/staging', {
        params: { status: 'pending', limit: 100 },
      })
      setItems(response.items ?? [])
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

  const getMergeTarget = useCallback(async (stagingItem: StagingKnowledgeItem): Promise<LegacyKnowledgeItem | undefined> => {
    if (!stagingItem.merge_with_id) return undefined
    
    try {
      const response = await apiRequest<MergeTargetResponse>(`/api/nodes/${stagingItem.merge_with_id}`)
      return {
        id: response.id,
        knowledge_type: 'faq',
        title: response.title,
        content: response.content,
        tags: response.tags,
        visibility: 'internal',
        status: 'published',
        created_at: new Date().toISOString(),
        variants_count: 0,
        relationships_count: 0,
        hits_count: 0,
      }
    } catch {
      return undefined
    }
  }, [])

  const approveItem = useCallback(async (
    id: number,
    options?: {
      editedContent?: Partial<StagingKnowledgeItem>
    }
  ): Promise<void> => {
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
