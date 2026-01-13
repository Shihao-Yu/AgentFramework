import { Building2, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { useTenantContext } from './TenantProvider'

interface TenantSelectorProps {
  mode?: 'single' | 'multi'
  showNodeCount?: boolean
  className?: string
}

export function TenantSelector({ 
  mode = 'multi', 
  showNodeCount = true,
  className 
}: TenantSelectorProps) {
  const {
    accessibleTenants,
    selectedTenantIds,
    currentTenantId,
    toggleTenant,
    setCurrentTenant,
  } = useTenantContext()

  const handleTenantChange = (tenantId: string) => {
    if (mode === 'single') {
      setCurrentTenant(tenantId)
    } else {
      toggleTenant(tenantId)
    }
  }

  const displayText = mode === 'single'
    ? accessibleTenants.find(t => t.tenant_id === currentTenantId)?.tenant_name || 'Select Tenant'
    : selectedTenantIds.length === 0
      ? 'Select Tenants'
      : selectedTenantIds.length === 1
        ? accessibleTenants.find(t => t.tenant_id === selectedTenantIds[0])?.tenant_name
        : `${selectedTenantIds.length} tenants`

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className={className}>
          <Building2 className="mr-2 h-4 w-4" />
          <span className="max-w-[150px] truncate">{displayText}</span>
          <ChevronDown className="ml-2 h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          {mode === 'single' ? 'Select Tenant' : 'Select Tenants'}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {accessibleTenants.map((tenant) => {
          const isSelected = mode === 'single'
            ? currentTenantId === tenant.tenant_id
            : selectedTenantIds.includes(tenant.tenant_id)

          return (
            <DropdownMenuCheckboxItem
              key={tenant.tenant_id}
              checked={isSelected}
              onCheckedChange={() => handleTenantChange(tenant.tenant_id)}
            >
              <div className="flex w-full items-center justify-between">
                <div className="flex items-center gap-2">
                  <span>{tenant.tenant_name}</span>
                  <Badge variant="outline" className="text-[10px] px-1">
                    {tenant.role}
                  </Badge>
                </div>
                {showNodeCount && tenant.node_count !== undefined && (
                  <span className="text-xs text-muted-foreground">
                    {tenant.node_count}
                  </span>
                )}
              </div>
            </DropdownMenuCheckboxItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
