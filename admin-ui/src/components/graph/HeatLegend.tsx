import { getHeatLegendItems } from '@/lib/heat-utils'
import { cn } from '@/lib/utils'

interface HeatLegendProps {
  className?: string
  compact?: boolean
}

export function HeatLegend({ className, compact = false }: HeatLegendProps) {
  const items = getHeatLegendItems()

  if (compact) {
    return (
      <div className={cn('flex items-center gap-1', className)}>
        <span className="text-xs text-muted-foreground mr-1">Cold</span>
        {items.map((item) => (
          <div
            key={item.level}
            className="h-3 w-6 rounded-sm border"
            style={{
              backgroundColor: item.colors.bg,
              borderColor: item.colors.border,
              borderStyle: item.level === 'never' ? 'dashed' : 'solid',
              opacity: item.level === 'never' ? 0.5 : 1,
            }}
            title={`${item.label}: ${item.description}`}
          />
        ))}
        <span className="text-xs text-muted-foreground ml-1">Hot</span>
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col gap-1.5 p-2 bg-background/80 rounded-md border', className)}>
      <span className="text-xs font-medium text-muted-foreground mb-1">Heat Scale</span>
      {items.map((item) => (
        <div key={item.level} className="flex items-center gap-2">
          <div
            className="h-4 w-8 rounded-sm border"
            style={{
              backgroundColor: item.colors.bg,
              borderColor: item.colors.border,
              borderStyle: item.level === 'never' ? 'dashed' : 'solid',
              opacity: item.level === 'never' ? 0.5 : 1,
            }}
          />
          <span className="text-xs text-muted-foreground">
            {item.label} ({item.description})
          </span>
        </div>
      ))}
    </div>
  )
}
