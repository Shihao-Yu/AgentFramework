import { createContext, useContext, useState, useCallback, useMemo, useEffect, type ReactNode } from 'react'
import { useTenants } from '@/hooks/useTenants'
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
  isLoading: boolean
  error: string | null
}

const TenantContext = createContext<TenantContextValue | null>(null)

interface TenantProviderProps {
  children: ReactNode
  defaultTenantId?: string
}

export function TenantProvider({ children, defaultTenantId }: TenantProviderProps) {
  const {
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
  } = useTenants()

  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null)

  useEffect(() => {
    if (!currentTenantId && selectedTenantIds.length > 0) {
      setCurrentTenantId(selectedTenantIds[0])
    }
  }, [currentTenantId, selectedTenantIds])

  useEffect(() => {
    if (defaultTenantId && accessibleTenants.some(t => t.tenant_id === defaultTenantId)) {
      if (!selectedTenantIds.includes(defaultTenantId)) {
        selectTenant(defaultTenantId)
      }
      if (!currentTenantId) {
        setCurrentTenantId(defaultTenantId)
      }
    }
  }, [defaultTenantId, accessibleTenants, selectedTenantIds, currentTenantId, selectTenant])

  const currentTenant = useMemo(() => {
    if (!currentTenantId) return null
    return tenants.find(t => t.id === currentTenantId) || null
  }, [tenants, currentTenantId])

  const setCurrentTenant = useCallback((tenantId: string) => {
    setCurrentTenantId(tenantId)
    if (!selectedTenantIds.includes(tenantId)) {
      selectTenant(tenantId)
    }
  }, [selectedTenantIds, selectTenant])

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
    isLoading,
    error,
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
