import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { NodeTypeConfig, type NodeType } from '@/types/graph'

export interface KnowledgeNodeData extends Record<string, unknown> {
  id: number
  nodeType: NodeType
  title: string
  summary?: string
  tags: string[]
  isSearchMatch?: boolean
}

export type KnowledgeNodeType = Node<KnowledgeNodeData, 'knowledge'>

const handleClassName = cn(
  '!w-3 !h-3 !bg-muted-foreground/50 !border-2 !border-background',
  'hover:!bg-blue-500 hover:!scale-150',
  'transition-all duration-150'
)

function KnowledgeNodeComponent({ data, selected }: NodeProps<KnowledgeNodeType>) {
  const nodeData = data as KnowledgeNodeData
  const config = NodeTypeConfig[nodeData.nodeType]

  return (
    <>
      <Handle 
        type="target" 
        position={Position.Top} 
        className={handleClassName}
      />
      <div
        className={cn(
          'min-w-[180px] max-w-[220px] rounded-lg border-2 px-3 py-2 shadow-md transition-all',
          selected && 'ring-2 ring-primary ring-offset-2',
          nodeData.isSearchMatch && 'ring-2 ring-yellow-400'
        )}
        style={{
          backgroundColor: config.bgColor,
          borderColor: config.color,
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg" role="img" aria-label={nodeData.nodeType}>
            {config.icon}
          </span>
          <span
            className="flex-1 truncate text-sm font-medium"
            style={{ color: config.color }}
          >
            {nodeData.title}
          </span>
        </div>
        {nodeData.summary && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {nodeData.summary}
          </p>
        )}
        {nodeData.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {nodeData.tags.slice(0, 2).map((tag: string) => (
              <span
                key={tag}
                className="rounded-full bg-background/50 px-1.5 py-0.5 text-[10px] text-muted-foreground"
              >
                {tag}
              </span>
            ))}
            {nodeData.tags.length > 2 && (
              <span className="text-[10px] text-muted-foreground">
                +{nodeData.tags.length - 2}
              </span>
            )}
          </div>
        )}
      </div>
      <Handle 
        type="source" 
        position={Position.Bottom} 
        className={handleClassName}
      />
    </>
  )
}

export const KnowledgeNode = memo(KnowledgeNodeComponent)
