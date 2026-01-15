import { useState, useCallback, useMemo, useEffect } from 'react'
import { apiRequest } from '@/lib/api'
import type { StagingKnowledgeItem, LegacyKnowledgeItem } from '@/types/knowledge'
import type { StagingEditData } from '@/components/staging'

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
  node_type: string
  title: string
  content: Record<string, unknown>
  tags: string[]
}

interface StagingCountsResponse {
  new: number
  merge: number
  add_variant: number
  total: number
}

export function useStaging() {
  const [items, setItems] = useState<StagingKnowledgeItem[]>([])
  const [countByAction, setCountByAction] = useState({
    new: 0,
    merge: 0,
    add_variant: 0,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pendingItems = useMemo(() => {
    return items.filter((item) => item.status === 'pending')
  }, [items])

  const fetchCounts = useCallback(async () => {
    try {
      const response = await apiRequest<StagingCountsResponse>('/api/staging/counts')
      setCountByAction({
        new: response.new,
        merge: response.merge,
        add_variant: response.add_variant,
      })
    } catch (err) {
      console.error('Failed to fetch staging counts:', err)
    }
  }, [])

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
    fetchCounts()
  }, [fetchItems, fetchCounts])

  const getMergeTarget = useCallback(async (stagingItem: StagingKnowledgeItem): Promise<LegacyKnowledgeItem | undefined> => {
    if (!stagingItem.merge_with_id) return undefined
    
    try {
      const response = await apiRequest<MergeTargetResponse>(`/api/nodes/${stagingItem.merge_with_id}`)
      return {
        id: response.id,
        // Use the actual node_type from the response, not hardcoded
        knowledge_type: response.node_type || stagingItem.node_type,
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
      fetchCounts()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to approve item'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [fetchCounts])

  const rejectItem = useCallback(async (id: number, reason?: string): Promise<void> => {
    setIsLoading(true)
    setError(null)
    
    try {
      await apiRequest<StagingReviewResponse>(`/api/staging/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      })
      
      setItems((prev) => prev.filter((item) => item.id !== id))
      fetchCounts()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reject item'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [fetchCounts])

  /**
   * Edit and approve a staging item.
   * Now accepts StagingEditData which contains the full content object,
   * supporting any node type (FAQ, Playbook, Permission, etc.)
   */
  const editAndApprove = useCallback(async (
    id: number,
    editedData: StagingEditData
  ): Promise<void> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const edits: Record<string, unknown> = {
        title: editedData.title,
        content: editedData.content,
        tags: editedData.tags,
      }

      await apiRequest<StagingReviewResponse>(`/api/staging/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({ edits }),
      })
      
      setItems((prev) => prev.filter((item) => item.id !== id))
      fetchCounts()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to edit and approve item'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [fetchCounts])

  const getItem = useCallback((id: number): StagingKnowledgeItem | undefined => {
    return items.find((item) => item.id === id)
  }, [items])

  const refetch = useCallback(() => {
    fetchItems()
    fetchCounts()
  }, [fetchItems, fetchCounts])

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
    refetch,
  }
}
