import { lazy, Suspense } from 'react'
import { cn } from '@/lib/utils'
import type { MonacoEditorProps, JSONEditorProps } from './MonacoEditorCore'

const MonacoEditorCore = lazy(() => 
  import('./MonacoEditorCore').then(mod => ({ default: mod.MonacoEditorCore }))
)

const JSONEditorCore = lazy(() => 
  import('./MonacoEditorCore').then(mod => ({ default: mod.JSONEditorCore }))
)

function EditorSkeleton({ height, className }: { height?: number | string; className?: string }) {
  return (
    <div 
      className={cn(
        'border rounded-md bg-muted/50 animate-pulse flex items-center justify-center',
        className
      )}
      style={{ height: height || 400 }}
    >
      <span className="text-muted-foreground text-sm">Loading editor...</span>
    </div>
  )
}

export type { MonacoLanguage } from './MonacoEditorCore'
export type { MonacoEditorProps, JSONEditorProps }

export function MonacoEditor(props: MonacoEditorProps) {
  return (
    <Suspense fallback={<EditorSkeleton height={props.height} className={props.className} />}>
      <MonacoEditorCore {...props} />
    </Suspense>
  )
}

export function JSONEditor(props: JSONEditorProps) {
  return (
    <Suspense fallback={<EditorSkeleton height={props.height} className={props.className} />}>
      <JSONEditorCore {...props} />
    </Suspense>
  )
}
