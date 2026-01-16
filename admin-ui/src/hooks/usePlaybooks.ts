import { useState, useCallback, useEffect } from 'react'
import { apiRequest } from '@/lib/api'
import type { PlaybookItem, PlaybookFormData, Domain } from '@/types/knowledge'
import { DEFAULT_DOMAINS } from '@/types/knowledge'

interface ApiNodeListResponse {
  data: Array<{
    id: number
    tenant_id: string
    node_type: string
    title: string
    summary?: string
    content: {
      domain: string
      content: string
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

// Custom domains storage key
const CUSTOM_DOMAINS_KEY = 'custom_domains'

interface PlaybookFilters {
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

export function usePlaybooks(tenantId?: string) {
  const [items, setItems] = useState<PlaybookItem[]>([])
  const [allTags, setAllTags] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<PlaybookFilters>({
    page: 1,
    limit: 100,
  })
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    limit: 100,
    total: 0,
    totalPages: 0,
  })

  // Domain management
  const [customDomains, setCustomDomains] = useState<Domain[]>(() => {
    try {
      const stored = localStorage.getItem(CUSTOM_DOMAINS_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  const allDomains = [...DEFAULT_DOMAINS, ...customDomains]

  const fetchItems = useCallback(async (currentFilters?: PlaybookFilters) => {
    const f = currentFilters || filters
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['playbook'],
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
      
      const playbookItems: PlaybookItem[] = response.data.map(node => ({
        id: node.id,
        knowledge_type: 'playbook',
        title: node.title,
        content: {
          domain: node.content.domain || '',
          content: node.content.content || '',
        },
        tags: node.tags,
        status: node.status as PlaybookItem['status'],
        visibility: node.visibility as PlaybookItem['visibility'],
        created_at: node.created_at,
        updated_at: node.updated_at,
      }))
      
      setItems(playbookItems)
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
      setAllTags(prev => {
        const merged = new Set([...prev, ...tagsFromResults])
        return Array.from(merged).sort()
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch playbooks'
      setError(message)
      console.error('Failed to fetch playbooks:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters, tenantId])

  // Fetch all tags on mount
  const fetchAllTags = useCallback(async () => {
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['playbook'],
        limit: '100',
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Update filters and refetch
  const updateFilters = useCallback((newFilters: Partial<PlaybookFilters>) => {
    setFilters(prev => {
      const updated = { ...prev, ...newFilters }
      if (newFilters.search !== undefined || newFilters.tags !== undefined) {
        updated.page = 1
      }
      fetchItems(updated)
      return updated
    })
  }, [fetchItems])

  const addCustomDomain = useCallback((name: string, description?: string) => {
    const newDomain: Domain = {
      id: name.toLowerCase().replace(/\s+/g, '-'),
      name,
      description,
      isCustom: true,
    }
    setCustomDomains((prev) => {
      const updated = [...prev, newDomain]
      localStorage.setItem(CUSTOM_DOMAINS_KEY, JSON.stringify(updated))
      return updated
    })
    return newDomain
  }, [])

  const removeCustomDomain = useCallback((id: string) => {
    setCustomDomains((prev) => {
      const updated = prev.filter((d) => d.id !== id)
      localStorage.setItem(CUSTOM_DOMAINS_KEY, JSON.stringify(updated))
      return updated
    })
  }, [])

  const createItem = useCallback(async (data: PlaybookFormData): Promise<PlaybookItem> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        id: number
        tenant_id: string
        node_type: string
        title: string
        content: {
          domain: string
          content: string
        }
        tags: string[]
        visibility: string
        status: string
        created_at: string
      }>('/api/nodes', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: tenantId || 'default',
          node_type: 'playbook',
          title: data.title,
          content: {
            domain: data.domain,
            content: data.content,
          },
          tags: data.tags,
          visibility: data.visibility,
          status: data.status,
        }),
      })
      
      const newItem: PlaybookItem = {
        id: response.id,
        knowledge_type: 'playbook',
        title: response.title,
        content: {
          domain: response.content.domain,
          content: response.content.content,
        },
        tags: response.tags,
        status: response.status as PlaybookItem['status'],
        visibility: response.visibility as PlaybookItem['visibility'],
        created_at: response.created_at,
      }
      
      await fetchItems()
      return newItem
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create playbook'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [tenantId, fetchItems])

  const updateItem = useCallback(async (id: number, data: PlaybookFormData): Promise<void> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        id: number
        title: string
        content: {
          domain: string
          content: string
        }
        tags: string[]
        visibility: string
        status: string
        updated_at: string
      }>(`/api/nodes/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: data.title,
          content: {
            domain: data.domain,
            content: data.content,
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
                domain: response.content.domain,
                content: response.content.content,
              },
              tags: response.tags,
              status: response.status as PlaybookItem['status'],
              visibility: response.visibility as PlaybookItem['visibility'],
              updated_at: response.updated_at,
            }
          : item
      ))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update playbook'
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
      const message = err instanceof Error ? err.message : 'Failed to delete playbook'
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
    domains: allDomains,
    customDomains,
    createItem,
    updateItem,
    deleteItem,
    updateFilters,
    addCustomDomain,
    removeCustomDomain,
    refetch: fetchItems,
  }
}
