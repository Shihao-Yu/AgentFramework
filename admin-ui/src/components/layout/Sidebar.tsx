import { useState, useMemo } from 'react'
import { NavLink } from 'react-router-dom'
import {
  MessageCircleQuestion,
  ShieldCheck,
  Database,
  BookMarked,
  Inbox,
  BarChart3,
  Settings,
  ChevronLeft,
  ChevronRight,
  BookOpen,
  Network,
  Package,
  Lightbulb,
  Activity,
  Upload,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useStaging } from '@/hooks/useStaging'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: number
}

const baseNavigation: Omit<NavItem, 'badge'>[] = [
  { name: 'Graph Explorer', href: '/graph', icon: Network },
  { name: 'FAQs', href: '/', icon: MessageCircleQuestion },
  { name: 'Feature & Permissions', href: '/permissions', icon: ShieldCheck },
  { name: 'Datasets', href: '/schemas', icon: Database },
  { name: 'Playbooks', href: '/playbooks', icon: BookMarked },
  { name: 'Entities', href: '/entities', icon: Package },
  { name: 'Concepts', href: '/concepts', icon: Lightbulb },
  { name: 'Context Onboarding', href: '/onboarding', icon: Upload },
  { name: 'Staging Queue', href: '/staging', icon: Inbox },
  { name: 'Usage Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Graph Health', href: '/graph-analytics', icon: Activity },
]

const secondaryNavigation: NavItem[] = [
  { name: 'Settings', href: '/settings', icon: Settings },
]

interface NavLinkItemProps {
  item: NavItem
  collapsed: boolean
  isSecondary?: boolean
}

function NavLinkItem({ item, collapsed, isSecondary = false }: NavLinkItemProps) {
  const linkContent = (
    <NavLink
      to={item.href}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
          isActive
            ? isSecondary
              ? 'bg-accent text-accent-foreground'
              : 'bg-primary text-primary-foreground shadow-sm'
            : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground',
          collapsed && 'justify-center px-2'
        )
      }
    >
      <item.icon className="h-5 w-5 shrink-0" aria-hidden="true" />
      {!collapsed && (
        <>
          <span className="flex-1">{item.name}</span>
          {item.badge !== undefined && item.badge > 0 && (
            <span 
              className="flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1.5 text-xs font-medium text-destructive-foreground"
              aria-label={`${item.badge} pending items`}
            >
              {item.badge}
            </span>
          )}
        </>
      )}
      {collapsed && item.badge !== undefined && item.badge > 0 && (
        <span 
          className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground"
          aria-label={`${item.badge} pending items`}
        >
          {item.badge}
        </span>
      )}
    </NavLink>
  )

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="relative">{linkContent}</div>
        </TooltipTrigger>
        <TooltipContent side="right" sideOffset={12}>
          <p>{item.name}</p>
          {item.badge !== undefined && item.badge > 0 && (
            <p className="text-xs text-muted-foreground">{item.badge} pending</p>
          )}
        </TooltipContent>
      </Tooltip>
    )
  }

  return linkContent
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { pendingItems } = useStaging()
  
  const navigation = useMemo<NavItem[]>(() => {
    return baseNavigation.map(item => {
      if (item.href === '/staging') {
        return { ...item, badge: pendingItems.length }
      }
      return item
    })
  }, [pendingItems.length])

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'flex flex-col border-r glass transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
        aria-label="Main navigation"
      >
        {/* Header */}
        <div className="flex h-16 items-center justify-between border-b border-border/50 px-2">
          {!collapsed && (
            <div className="flex items-center gap-3 px-3">
              <BookOpen className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
              <span className="font-semibold tracking-tight text-sm whitespace-nowrap">Context Management</span>
            </div>
          )}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCollapsed(!collapsed)}
                className={cn(
                  'h-8 w-8 shrink-0',
                  collapsed && 'mx-auto'
                )}
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                aria-expanded={!collapsed}
              >
                {collapsed ? (
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side={collapsed ? 'right' : 'bottom'} sideOffset={8}>
              <p>{collapsed ? 'Expand sidebar' : 'Collapse sidebar'}</p>
            </TooltipContent>
          </Tooltip>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 space-y-1 p-2" aria-label="Primary">
          {navigation.map((item) => (
            <NavLinkItem 
              key={item.href} 
              item={item} 
              collapsed={collapsed} 
            />
          ))}
        </nav>

        <Separator className="opacity-50" />

        {/* Secondary Navigation */}
        <nav className="space-y-1 p-2" aria-label="Secondary">
          {secondaryNavigation.map((item) => (
            <NavLinkItem
              key={item.href}
              item={item}
              collapsed={collapsed}
              isSecondary
            />
          ))}
        </nav>

        {!collapsed && (
          <div className="border-t border-border/50 p-4 mt-auto">
            <p className="text-xs text-muted-foreground">
              Knowledge Base Admin v1.0
            </p>
          </div>
        )}
      </aside>
    </TooltipProvider>
  )
}
