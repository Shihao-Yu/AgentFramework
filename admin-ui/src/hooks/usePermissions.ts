import { useState, useCallback, useMemo, useEffect } from 'react'
import { apiRequest } from '@/lib/api'
import type { PermissionItem, PermissionFormData } from '@/types/knowledge'

interface ApiNodeListResponse {
  data: Array<{
    id: number
    tenant_id: string
    node_type: string
    title: string
    summary?: string
    content: {
      description: string
      permissions: string[]
      roles: string[]
      context?: string
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

interface PermissionFilters {
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

export function usePermissions(tenantId?: string) {
  const [items, setItems] = useState<PermissionItem[]>([])
  const [allTags, setAllTags] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<PermissionFilters>({
    page: 1,
    limit: 100,
  })
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    limit: 100,
    total: 0,
    totalPages: 0,
  })

  const fetchItems = useCallback(async (currentFilters?: PermissionFilters) => {
    const f = currentFilters || filters
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['permission_rule'],
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
      
      const permissionItems: PermissionItem[] = response.data.map(node => ({
        id: node.id,
        knowledge_type: 'permission',
        title: node.title,
        content: {
          description: node.content.description || '',
          permissions: node.content.permissions || [],
          roles: node.content.roles || [],
          context: node.content.context,
        },
        tags: node.tags,
        status: node.status as PermissionItem['status'],
        visibility: node.visibility as PermissionItem['visibility'],
        created_at: node.created_at,
        updated_at: node.updated_at,
      }))
      
      setItems(permissionItems)
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
      const message = err instanceof Error ? err.message : 'Failed to fetch permissions'
      setError(message)
      console.error('Failed to fetch permissions:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters, tenantId])

  // Fetch all tags on mount
  const fetchAllTags = useCallback(async () => {
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['permission_rule'],
        limit: '1000',
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
  }, [])

  // Update filters and refetch
  const updateFilters = useCallback((newFilters: Partial<PermissionFilters>) => {
    setFilters(prev => {
      const updated = { ...prev, ...newFilters }
      if (newFilters.search !== undefined || newFilters.tags !== undefined) {
        updated.page = 1
      }
      fetchItems(updated)
      return updated
    })
  }, [fetchItems])

  const existingPermissions = useMemo(() => {
    const allPerms = new Set<string>()
    items.forEach((item) => {
      item.content.permissions.forEach((p) => allPerms.add(p))
    })
    return Array.from(allPerms).sort()
  }, [items])

  const existingRoles = useMemo(() => {
    const allRoles = new Set<string>()
    items.forEach((item) => {
      item.content.roles.forEach((r) => allRoles.add(r))
    })
    return Array.from(allRoles).sort()
  }, [items])

  const createItem = useCallback(async (data: PermissionFormData): Promise<PermissionItem> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        id: number
        tenant_id: string
        node_type: string
        title: string
        content: {
          description: string
          permissions: string[]
          roles: string[]
          context?: string
        }
        tags: string[]
        visibility: string
        status: string
        created_at: string
      }>('/api/nodes', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: tenantId || 'default',
          node_type: 'permission_rule',
          title: data.title,
          content: {
            description: data.description,
            permissions: data.permissions,
            roles: data.roles,
            context: data.context,
          },
          tags: data.tags,
          visibility: data.visibility,
          status: data.status,
        }),
      })
      
      const newItem: PermissionItem = {
        id: response.id,
        knowledge_type: 'permission',
        title: response.title,
        content: {
          description: response.content.description,
          permissions: response.content.permissions,
          roles: response.content.roles,
          context: response.content.context,
        },
        tags: response.tags,
        status: response.status as PermissionItem['status'],
        visibility: response.visibility as PermissionItem['visibility'],
        created_at: response.created_at,
      }
      
      await fetchItems()
      return newItem
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create permission'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [tenantId, fetchItems])

  const updateItem = useCallback(async (id: number, data: PermissionFormData): Promise<void> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        id: number
        title: string
        content: {
          description: string
          permissions: string[]
          roles: string[]
          context?: string
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
            description: data.description,
            permissions: data.permissions,
            roles: data.roles,
            context: data.context,
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
                description: response.content.description,
                permissions: response.content.permissions,
                roles: response.content.roles,
                context: response.content.context,
              },
              tags: response.tags,
              status: response.status as PermissionItem['status'],
              visibility: response.visibility as PermissionItem['visibility'],
              updated_at: response.updated_at,
            }
          : item
      ))
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update permission'
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
      const message = err instanceof Error ? err.message : 'Failed to delete permission'
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
    existingPermissions,
    existingRoles,
    createItem,
    updateItem,
    deleteItem,
    updateFilters,
    refetch: fetchItems,
  }
}
