import { useCallback, useMemo, useState, useEffect } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type Connection,
  ConnectionLineType,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { KnowledgeNode, type KnowledgeNodeData } from './nodes/KnowledgeNode'
import { CustomEdge, type CustomEdgeData } from './CustomEdge'
import { HeatLegend } from './HeatLegend'
import { getLayoutedElements, type LayoutDirection } from '@/lib/graph-layout'
import { useHeatmap, type HeatmapPeriod, type HeatmapNodeData } from '@/hooks/useHeatmap'
import { getHeatBgColor } from '@/lib/heat-utils'
import type { GraphNode, GraphEdge, GraphViewMode } from '@/types/graph'

const nodeTypes = {
  knowledge: KnowledgeNode,
}

const edgeTypes = {
  custom: CustomEdge,
}

export interface GraphCanvasProps {
  graphNodes: GraphNode[]
  graphEdges: GraphEdge[]
  searchMatches?: number[]
  onNodeSelect?: (nodeId: number | null) => void
  onNodeDoubleClick?: (nodeId: number) => void
  onEdgeCreate?: (sourceId: number, targetId: number) => void
  className?: string
  enableHeatmap?: boolean
}

function transformToReactFlowNodes(
  graphNodes: GraphNode[],
  searchMatches: number[] = [],
  viewMode: GraphViewMode = 'type',
  heatmapData?: Map<number, HeatmapNodeData>
): Node<KnowledgeNodeData>[] {
  const searchMatchSet = new Set(searchMatches)
  
  return graphNodes.map((node) => {
    const heatData = heatmapData?.get(node.id)
    
    return {
      id: String(node.id),
      type: 'knowledge',
      position: { x: node.x || 0, y: node.y || 0 },
      data: {
        id: node.id,
        nodeType: node.node_type,
        title: node.title,
        summary: node.summary,
        tags: node.tags,
        isSearchMatch: searchMatchSet.has(node.id),
        viewMode,
        heatData: heatData ? {
          heatScore: heatData.heat_score,
          totalHits: heatData.total_hits,
          uniqueSessions: heatData.unique_sessions,
          lastHitAt: heatData.last_hit_at ?? undefined,
        } : undefined,
      },
    }
  })
}

function transformToReactFlowEdges(graphEdges: GraphEdge[]): Edge<CustomEdgeData>[] {
  return graphEdges.map((edge, index) => ({
    id: `e-${edge.source}-${edge.target}-${index}`,
    source: String(edge.source),
    target: String(edge.target),
    type: 'custom',
    data: {
      edgeType: edge.edge_type,
      weight: edge.weight,
    },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 15,
      height: 15,
    },
  }))
}

export function GraphCanvasCore({
  graphNodes,
  graphEdges,
  searchMatches = [],
  onNodeSelect,
  onNodeDoubleClick,
  onEdgeCreate,
  className,
  enableHeatmap = true,
}: GraphCanvasProps) {
  const [layoutDirection, setLayoutDirection] = useState<LayoutDirection>('TB')
  const [viewMode, setViewMode] = useState<GraphViewMode>('type')
  const [heatPeriod, setHeatPeriod] = useState<HeatmapPeriod>('7d')
  
  const { heatmapData, stats, isLoading: isHeatmapLoading } = useHeatmap({
    period: heatPeriod,
    enabled: enableHeatmap && viewMode === 'heat',
  })

  const initialNodes = useMemo(
    () => transformToReactFlowNodes(graphNodes, searchMatches, viewMode, viewMode === 'heat' ? heatmapData : undefined),
    [graphNodes, searchMatches, viewMode, heatmapData]
  )

  const initialEdges = useMemo(
    () => transformToReactFlowEdges(graphEdges),
    [graphEdges]
  )

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(initialNodes, initialEdges, { direction: layoutDirection }),
    [initialNodes, initialEdges, layoutDirection]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutedNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutedEdges)

  useEffect(() => {
    setNodes(layoutedNodes)
  }, [layoutedNodes, setNodes])

  useEffect(() => {
    setEdges(layoutedEdges)
  }, [layoutedEdges, setEdges])

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (connection.source && connection.target && connection.source !== connection.target) {
        onEdgeCreate?.(Number(connection.source), Number(connection.target))
      }
    },
    [onEdgeCreate]
  )

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      onNodeSelect?.(Number(node.id))
    },
    [onNodeSelect]
  )

  const handleNodeDoubleClick: NodeMouseHandler = useCallback(
    (_, node) => {
      onNodeDoubleClick?.(Number(node.id))
    },
    [onNodeDoubleClick]
  )

  const handlePaneClick = useCallback(() => {
    onNodeSelect?.(null)
  }, [onNodeSelect])

  const handleLayout = useCallback(
    (direction: LayoutDirection) => {
      setLayoutDirection(direction)
      const { nodes: newNodes, edges: newEdges } = getLayoutedElements(
        nodes,
        edges,
        { direction }
      )
      setNodes([...newNodes])
      setEdges([...newEdges])
    },
    [nodes, edges, setNodes, setEdges]
  )

  return (
    <div className={className}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onNodeClick={handleNodeClick}
        onNodeDoubleClick={handleNodeDoubleClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionLineType={ConnectionLineType.SmoothStep}
        connectionLineStyle={{ stroke: '#3b82f6', strokeWidth: 2 }}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.1}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} />
        <Controls showInteractive={false} />
        <MiniMap
          nodeStrokeWidth={3}
          zoomable
          pannable
          className="!bg-background/80"
          nodeColor={viewMode === 'heat' 
            ? (node) => getHeatBgColor((node.data as KnowledgeNodeData).heatData?.heatScore)
            : undefined
          }
        />
        
        <Panel position="top-right" className="flex flex-col gap-2">
          <div className="flex gap-1">
            <Button
              variant={layoutDirection === 'TB' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleLayout('TB')}
            >
              Vertical
            </Button>
            <Button
              variant={layoutDirection === 'LR' ? 'default' : 'outline'}
              size="sm"
              onClick={() => handleLayout('LR')}
            >
              Horizontal
            </Button>
          </div>
          
          {enableHeatmap && (
            <div className="flex gap-1 items-center bg-background/80 rounded-md p-1">
              <Button
                variant={viewMode === 'type' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('type')}
              >
                Type
              </Button>
              <Button
                variant={viewMode === 'heat' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('heat')}
                disabled={isHeatmapLoading && viewMode !== 'heat'}
              >
                {isHeatmapLoading && viewMode === 'heat' ? 'Loading...' : 'Heat'}
              </Button>
              
              {viewMode === 'heat' && (
                <Select value={heatPeriod} onValueChange={(v) => setHeatPeriod(v as HeatmapPeriod)}>
                  <SelectTrigger className="w-[80px] h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="7d">7 days</SelectItem>
                    <SelectItem value="30d">30 days</SelectItem>
                    <SelectItem value="90d">90 days</SelectItem>
                    <SelectItem value="all">All time</SelectItem>
                  </SelectContent>
                </Select>
              )}
            </div>
          )}
        </Panel>
        
        {viewMode === 'heat' && (
          <Panel position="bottom-left">
            <HeatLegend compact />
            {stats && (
              <div className="mt-1 text-xs text-muted-foreground">
                {stats.nodes_with_hits}/{stats.total_nodes} nodes with hits
              </div>
            )}
          </Panel>
        )}
      </ReactFlow>
    </div>
  )
}
