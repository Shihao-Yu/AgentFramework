import { useState, useCallback, useEffect, useMemo } from 'react'
import { apiRequest } from '@/lib/api'
import type { FAQItem, FAQFormData } from '@/types/knowledge'

interface ApiNodeListResponse {
  data: Array<{
    id: number
    tenant_id: string
    node_type: string
    title: string
    summary?: string
    content: {
      question: string
      answer: string
      variants?: string[]
    }
    tags: string[]
    visibility: string
    status: string
    created_at: string
    updated_at?: string
  }>
  total: number
  page: number
  limit: number
  total_pages: number
}

interface FAQFilters {
  search?: string
  tags?: string[]
  page?: number
  limit?: number
}

interface PaginationInfo {
  page: number
  limit: number
  total: number
  totalPages: number
}

export function useFAQs(tenantId?: string) {
  const [items, setItems] = useState<FAQItem[]>([])
  const [allTags, setAllTags] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FAQFilters>({
    page: 1,
    limit: 100,
  })
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    limit: 100,
    total: 0,
    totalPages: 0,
  })

  const fetchItems = useCallback(async (currentFilters?: FAQFilters) => {
    const f = currentFilters || filters
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['faq'],
        limit: String(f.limit || 100),
        page: String(f.page || 1),
      }
      
      if (tenantId) {
        params.tenant_ids = [tenantId]
      }
      
      if (f.search && f.search.trim()) {
        params.search = f.search.trim()
      }
      
      if (f.tags && f.tags.length > 0) {
        params.tags = f.tags
      }
      
      const response = await apiRequest<ApiNodeListResponse>('/api/nodes', { params })
      
      const faqItems: FAQItem[] = response.data.map(node => ({
        id: node.id,
        knowledge_type: 'faq',
        title: node.title,
        content: {
          question: node.content.question || node.title,
          answer: node.content.answer || '',
        },
        tags: node.tags,
        status: node.status as FAQItem['status'],
        visibility: node.visibility as FAQItem['visibility'],
        created_at: node.created_at,
        updated_at: node.updated_at,
      }))
      
      setItems(faqItems)
      setPagination({
        page: response.page,
        limit: response.limit,
        total: response.total,
        totalPages: response.total_pages,
      })
      
      // Collect all unique tags from results for the filter
      const tagsFromResults = new Set<string>()
      response.data.forEach(node => {
        node.tags.forEach(tag => tagsFromResults.add(tag))
      })
      // Merge with existing tags to keep filter options stable
      setAllTags(prev => {
        const merged = new Set([...prev, ...tagsFromResults])
        return Array.from(merged).sort()
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch FAQs'
      setError(message)
      console.error('Failed to fetch FAQs:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters, tenantId])

  // Fetch all tags on mount (separate call without filters to get all available tags)
  const fetchAllTags = useCallback(async () => {
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['faq'],
        limit: '1000', // Get all to collect tags
      }
      if (tenantId) {
        params.tenant_ids = [tenantId]
      }
      const response = await apiRequest<ApiNodeListResponse>('/api/nodes', { params })
      const tags = new Set<string>()
      response.data.forEach(node => {
        node.tags.forEach(tag => tags.add(tag))
      })
      setAllTags(Array.from(tags).sort())
    } catch (err) {
      console.error('Failed to fetch tags:', err)
    }
  }, [tenantId])

  useEffect(() => {
    fetchItems()
    fetchAllTags()
  }, []) // Only run on mount

  // Update filters and refetch
  const updateFilters = useCallback((newFilters: Partial<FAQFilters>) => {
    setFilters(prev => {
      const updated = { ...prev, ...newFilters }
      // Reset to page 1 when search or tags change
      if (newFilters.search !== undefined || newFilters.tags !== undefined) {
        updated.page = 1
      }
      fetchItems(updated)
      return updated
    })
  }, [fetchItems])

  const createItem = useCallback(async (data: FAQFormData): Promise<FAQItem> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        id: number
        tenant_id: string
        node_type: string
        title: string
        content: { question: string; answer: string }
        tags: string[]
        visibility: string
        status: string
        created_at: string
      }>('/api/nodes', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: tenantId || 'default',
          node_type: 'faq',
          title: data.title,
          content: {
            question: data.question,
            answer: data.answer,
          },
          tags: data.tags,
          visibility: data.visibility,
          status: data.status,
        }),
      })
      
      const newItem: FAQItem = {
        id: response.id,
        knowledge_type: 'faq',
        title: response.title,
        content: {
          question: response.content.question,
          answer: response.content.answer,
        },
        tags: response.tags,
        status: response.status as FAQItem['status'],
        visibility: response.visibility as FAQItem['visibility'],
        created_at: response.created_at,
      }
      
      // Refetch to get updated list
      await fetchItems()
      
      return newItem
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create FAQ'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [tenantId, fetchItems])

  const updateItem = useCallback(async (id: number, data: FAQFormData): Promise<void> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        id: number
        title: string
        content: { question: string; answer: string }
        tags: string[]
        visibility: string
        status: string
        updated_at: string
      }>(`/api/nodes/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: data.title,
          content: {
            question: data.question,
            answer: data.answer,
          },
          tags: data.tags,
          visibility: data.visibility,
          status: data.status,
        }),
      })
      
      setItems(prev => prev.map(item => 
        item.id === id
          ? {
              ...item,
              title: response.title,
              content: {
                question: response.content.question,
                answer: response.content.answer,
              },
              tags: response.tags,
              status: response.status as FAQItem['status'],
              visibility: response.visibility as FAQItem['visibility'],
              updated_at: response.updated_at,
            }
          : item
      ))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update FAQ'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteItem = useCallback(async (id: number): Promise<void> => {
    setIsLoading(true)
    setError(null)
    
    try {
      await apiRequest(`/api/nodes/${id}`, { method: 'DELETE' })
      setItems(prev => prev.filter(item => item.id !== id))
      setPagination(prev => ({ ...prev, total: prev.total - 1 }))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete FAQ'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    items,
    allTags,
    pagination,
    filters,
    isLoading,
    error,
    createItem,
    updateItem,
    deleteItem,
    updateFilters,
    refetch: fetchItems,
  }
}
