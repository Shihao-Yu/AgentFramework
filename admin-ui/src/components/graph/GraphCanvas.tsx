import { lazy, Suspense } from 'react'
import { cn } from '@/lib/utils'
import type { GraphCanvasProps } from './GraphCanvasCore'

const GraphCanvasCore = lazy(() => 
  import('./GraphCanvasCore').then(mod => ({ default: mod.GraphCanvasCore }))
)

function GraphSkeleton({ className }: { className?: string }) {
  return (
    <div 
      className={cn(
        'bg-muted/30 animate-pulse flex items-center justify-center rounded-md border',
        className
      )}
      style={{ minHeight: 400 }}
    >
      <div className="flex flex-col items-center gap-2 text-muted-foreground">
        <div className="h-8 w-8 rounded-full border-2 border-muted-foreground/30 border-t-muted-foreground animate-spin" />
        <span className="text-sm">Loading graph...</span>
      </div>
    </div>
  )
}

export type { GraphCanvasProps }

export function GraphCanvas(props: GraphCanvasProps) {
  return (
    <Suspense fallback={<GraphSkeleton className={props.className} />}>
      <GraphCanvasCore {...props} />
    </Suspense>
  )
}
