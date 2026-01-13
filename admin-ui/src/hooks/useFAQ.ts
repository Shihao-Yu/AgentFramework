import { useState, useCallback, useEffect } from 'react'
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

export function useFAQs(tenantId?: string) {
  const [items, setItems] = useState<FAQItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['faq'],
        limit: '100',
      }
      
      if (tenantId) {
        params.tenant_ids = [tenantId]
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch FAQs'
      setError(message)
      console.error('Failed to fetch FAQs:', err)
    } finally {
      setIsLoading(false)
    }
  }, [tenantId])

  useEffect(() => {
    fetchItems()
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
      
      setItems(prev => [newItem, ...prev])
      return newItem
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create FAQ'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [tenantId])

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
    isLoading,
    error,
    createItem,
    updateItem,
    deleteItem,
    refetch: fetchItems,
  }
}
