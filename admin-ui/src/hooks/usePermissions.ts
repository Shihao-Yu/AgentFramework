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

export function usePermissions(tenantId?: string) {
  const [items, setItems] = useState<PermissionItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | string[]> = {
        node_types: ['permission'],
        limit: '100',
      }
      
      if (tenantId) {
        params.tenant_ids = [tenantId]
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch permissions'
      setError(message)
      console.error('Failed to fetch permissions:', err)
    } finally {
      setIsLoading(false)
    }
  }, [tenantId])

  useEffect(() => {
    fetchItems()
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
          node_type: 'permission',
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
      
      setItems(prev => [newItem, ...prev])
      return newItem
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create permission'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [tenantId])

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
    isLoading,
    error,
    existingPermissions,
    existingRoles,
    createItem,
    updateItem,
    deleteItem,
    refetch: fetchItems,
  }
}
