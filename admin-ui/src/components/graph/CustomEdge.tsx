import { memo } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
  type Edge,
} from '@xyflow/react'
import { EdgeTypeConfig, EdgeTypeLabels, type EdgeType } from '@/types/graph'

export interface CustomEdgeData extends Record<string, unknown> {
  edgeType: EdgeType
  weight: number
}

export type CustomEdgeType = Edge<CustomEdgeData, 'custom'>

function CustomEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<CustomEdgeType>) {
  const edgeData = data as CustomEdgeData | undefined
  const config = edgeData?.edgeType ? EdgeTypeConfig[edgeData.edgeType] : EdgeTypeConfig.related
  const label = edgeData?.edgeType ? EdgeTypeLabels[edgeData.edgeType] : 'Related'

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: config.color,
          strokeWidth: selected ? 3 : 2,
          strokeDasharray: config.strokeDasharray,
        }}
        className={config.animated ? 'react-flow__edge-path-animated' : undefined}
      />
      {selected && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="rounded bg-background px-2 py-1 text-xs font-medium shadow-sm"
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export const CustomEdge = memo(CustomEdgeComponent)
