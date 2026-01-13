import { useState, useCallback, useMemo, useEffect } from 'react'
import { apiRequest } from '@/lib/api'
import type { Tenant, TenantAccess } from '@/types/graph'

interface UserTenantsResponse {
  user_id: string
  tenants: Array<{
    user_id: string
    tenant_id: string
    role: 'viewer' | 'editor' | 'admin'
    granted_at: string
    granted_by?: string
    tenant_name?: string
  }>
}

interface TenantListResponse {
  tenants: Array<{
    id: string
    name: string
    description?: string
    settings?: Record<string, unknown>
    is_active: boolean
    created_at: string
    updated_at?: string
    node_count?: number
    user_count?: number
  }>
  total: number
}

export function useTenants() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [access, setAccess] = useState<TenantAccess[]>([])
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch tenants and access on mount
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)
      
      try {
        // Fetch user's tenant access
        const accessResponse = await apiRequest<UserTenantsResponse>('/api/tenants/me')
        
        const tenantAccess: TenantAccess[] = accessResponse.tenants.map(t => ({
          tenant_id: t.tenant_id,
          tenant_name: t.tenant_name || t.tenant_id,
          role: t.role,
        }))
        setAccess(tenantAccess)
        
        // Set default selected tenant (first one)
        if (tenantAccess.length > 0 && selectedTenantIds.length === 0) {
          setSelectedTenantIds([tenantAccess[0].tenant_id])
        }
        
        // Fetch full tenant list
        const tenantsResponse = await apiRequest<TenantListResponse>('/api/tenants')
        
        const tenantList: Tenant[] = tenantsResponse.tenants.map(t => ({
          id: t.id,
          name: t.name,
          description: t.description,
          settings: t.settings,
          is_active: t.is_active,
          created_at: t.created_at,
          updated_at: t.updated_at,
        }))
        setTenants(tenantList)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to fetch tenants'
        setError(message)
        console.error('Failed to fetch tenants:', err)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchData()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const accessibleTenants = useMemo(() => {
    return access.map(a => ({
      ...a,
      tenant: tenants.find(t => t.id === a.tenant_id),
    }))
  }, [tenants, access])

  const selectedTenants = useMemo(() => {
    return accessibleTenants.filter(t => selectedTenantIds.includes(t.tenant_id))
  }, [accessibleTenants, selectedTenantIds])

  const canEdit = useCallback((tenantId: string): boolean => {
    const tenantAccess = access.find(a => a.tenant_id === tenantId)
    return tenantAccess?.role === 'admin' || tenantAccess?.role === 'editor'
  }, [access])

  const canAdmin = useCallback((tenantId: string): boolean => {
    const tenantAccess = access.find(a => a.tenant_id === tenantId)
    return tenantAccess?.role === 'admin'
  }, [access])

  const selectTenant = useCallback((tenantId: string) => {
    setSelectedTenantIds(prev => {
      if (prev.includes(tenantId)) return prev
      return [...prev, tenantId]
    })
  }, [])

  const deselectTenant = useCallback((tenantId: string) => {
    setSelectedTenantIds(prev => prev.filter(id => id !== tenantId))
  }, [])

  const toggleTenant = useCallback((tenantId: string) => {
    setSelectedTenantIds(prev => {
      if (prev.includes(tenantId)) {
        return prev.filter(id => id !== tenantId)
      }
      return [...prev, tenantId]
    })
  }, [])

  const setSelectedTenants = useCallback((tenantIds: string[]) => {
    setSelectedTenantIds(tenantIds)
  }, [])

  const getTenant = useCallback(async (tenantId: string): Promise<Tenant | null> => {
    try {
      const response = await apiRequest<{
        id: string
        name: string
        description?: string
        settings?: Record<string, unknown>
        is_active: boolean
        created_at: string
        updated_at?: string
      }>(`/api/tenants/${tenantId}`)
      
      return {
        id: response.id,
        name: response.name,
        description: response.description,
        settings: response.settings,
        is_active: response.is_active,
        created_at: response.created_at,
        updated_at: response.updated_at,
      }
    } catch (err) {
      console.error(`Failed to fetch tenant ${tenantId}:`, err)
      return null
    }
  }, [])

  const refetch = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const accessResponse = await apiRequest<UserTenantsResponse>('/api/tenants/me')
      
      const tenantAccess: TenantAccess[] = accessResponse.tenants.map(t => ({
        tenant_id: t.tenant_id,
        tenant_name: t.tenant_name || t.tenant_id,
        role: t.role,
      }))
      setAccess(tenantAccess)
      
      const tenantsResponse = await apiRequest<TenantListResponse>('/api/tenants')
      
      const tenantList: Tenant[] = tenantsResponse.tenants.map(t => ({
        id: t.id,
        name: t.name,
        description: t.description,
        settings: t.settings,
        is_active: t.is_active,
        created_at: t.created_at,
        updated_at: t.updated_at,
      }))
      setTenants(tenantList)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch tenants'
      setError(message)
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    tenants,
    accessibleTenants,
    selectedTenantIds,
    selectedTenants,
    isLoading,
    error,
    canEdit,
    canAdmin,
    selectTenant,
    deselectTenant,
    toggleTenant,
    setSelectedTenants,
    getTenant,
    refetch,
  }
}
