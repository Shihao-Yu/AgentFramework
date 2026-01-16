import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import { cn } from '@/lib/utils'
import { NodeTypeConfig, type NodeType, type NodeHeatData } from '@/types/graph'
import { getHeatColors, getHeatLevel, formatHitsCount } from '@/lib/heat-utils'

export interface KnowledgeNodeData extends Record<string, unknown> {
  id: number
  nodeType: NodeType
  title: string
  summary?: string
  tags: string[]
  isSearchMatch?: boolean
  viewMode?: 'type' | 'heat'
  heatData?: NodeHeatData
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
  
  const isHeatMode = nodeData.viewMode === 'heat'
  const heatScore = nodeData.heatData?.heatScore
  const heatLevel = isHeatMode ? getHeatLevel(heatScore) : null
  const heatColors = isHeatMode ? getHeatColors(heatScore) : null
  const isNeverAccessed = heatLevel === 'never'

  const bgColor = isHeatMode ? heatColors!.bg : config.bgColor
  const borderColor = isHeatMode ? heatColors!.border : config.color
  const textColor = isHeatMode ? heatColors!.text : config.color

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
          nodeData.isSearchMatch && 'ring-2 ring-yellow-400',
          isNeverAccessed && 'opacity-50'
        )}
        style={{
          backgroundColor: bgColor,
          borderColor: borderColor,
          borderStyle: isNeverAccessed ? 'dashed' : 'solid',
          boxShadow: (heatLevel === 'hot' || heatLevel === 'fire') 
            ? `0 0 12px ${borderColor}` 
            : undefined,
        }}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg" role="img" aria-label={nodeData.nodeType}>
            {config.icon}
          </span>
          <span
            className="flex-1 truncate text-sm font-medium"
            style={{ color: textColor }}
          >
            {nodeData.title}
          </span>
        </div>
        
        {isHeatMode && nodeData.heatData && (
          <div className="mt-1 flex items-center gap-2 text-[10px]" style={{ color: textColor }}>
            <span>{formatHitsCount(nodeData.heatData.totalHits)} hits</span>
            <span className="opacity-60">|</span>
            <span>{Math.round((heatScore ?? 0) * 100)}%</span>
          </div>
        )}
        
        {!isHeatMode && nodeData.summary && (
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
