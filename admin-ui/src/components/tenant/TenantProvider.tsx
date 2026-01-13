import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react'
import { mockTenants, mockTenantAccess } from '@/data/graph-mock-data'
import type { Tenant, TenantAccess } from '@/types/graph'

interface TenantContextValue {
  tenants: Tenant[]
  accessibleTenants: (TenantAccess & { tenant?: Tenant })[]
  selectedTenantIds: string[]
  selectedTenants: (TenantAccess & { tenant?: Tenant })[]
  currentTenantId: string | null
  currentTenant: Tenant | null
  selectTenant: (tenantId: string) => void
  deselectTenant: (tenantId: string) => void
  toggleTenant: (tenantId: string) => void
  setSelectedTenants: (tenantIds: string[]) => void
  setCurrentTenant: (tenantId: string) => void
  canEdit: (tenantId: string) => boolean
  canAdmin: (tenantId: string) => boolean
}

const TenantContext = createContext<TenantContextValue | null>(null)

interface TenantProviderProps {
  children: ReactNode
  defaultTenantId?: string
}

export function TenantProvider({ children, defaultTenantId = 'purchasing' }: TenantProviderProps) {
  const [tenants] = useState<Tenant[]>(mockTenants)
  const [access] = useState<TenantAccess[]>(mockTenantAccess)
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([defaultTenantId])
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(defaultTenantId)

  const accessibleTenants = useMemo(() => {
    return access.map(a => ({
      ...a,
      tenant: tenants.find(t => t.id === a.tenant_id),
    }))
  }, [tenants, access])

  const selectedTenants = useMemo(() => {
    return accessibleTenants.filter(t => selectedTenantIds.includes(t.tenant_id))
  }, [accessibleTenants, selectedTenantIds])

  const currentTenant = useMemo(() => {
    if (!currentTenantId) return null
    return tenants.find(t => t.id === currentTenantId) || null
  }, [tenants, currentTenantId])

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

  const setCurrentTenant = useCallback((tenantId: string) => {
    setCurrentTenantId(tenantId)
    if (!selectedTenantIds.includes(tenantId)) {
      setSelectedTenantIds(prev => [...prev, tenantId])
    }
  }, [selectedTenantIds])

  const value: TenantContextValue = {
    tenants,
    accessibleTenants,
    selectedTenantIds,
    selectedTenants,
    currentTenantId,
    currentTenant,
    selectTenant,
    deselectTenant,
    toggleTenant,
    setSelectedTenants,
    setCurrentTenant,
    canEdit,
    canAdmin,
  }

  return (
    <TenantContext.Provider value={value}>
      {children}
    </TenantContext.Provider>
  )
}

export function useTenantContext(): TenantContextValue {
  const context = useContext(TenantContext)
  if (!context) {
    throw new Error('useTenantContext must be used within a TenantProvider')
  }
  return context
}
