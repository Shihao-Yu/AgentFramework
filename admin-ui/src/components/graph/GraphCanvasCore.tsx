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
  ConnectionLineType,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Link2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { KnowledgeNode, type KnowledgeNodeData } from './nodes/KnowledgeNode'
import { CustomEdge, type CustomEdgeData } from './CustomEdge'
import { getLayoutedElements, type LayoutDirection } from '@/lib/graph-layout'
import type { GraphNode, GraphEdge } from '@/types/graph'

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
  edgeCreationMode?: boolean
  onEdgeCreationModeChange?: (enabled: boolean) => void
  pendingEdgeSource?: number | null
  onPendingEdgeSourceChange?: (nodeId: number | null) => void
  onEdgeCreate?: (sourceId: number, targetId: number) => void
  className?: string
}

function transformToReactFlowNodes(
  graphNodes: GraphNode[],
  searchMatches: number[] = [],
  edgeCreationMode: boolean = false,
  pendingEdgeSource: number | null = null
): Node<KnowledgeNodeData>[] {
  const searchMatchSet = new Set(searchMatches)
  
  return graphNodes.map((node) => ({
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
      isEdgeCreationMode: edgeCreationMode,
      isPendingSource: pendingEdgeSource === node.id,
    },
  }))
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
  edgeCreationMode = false,
  onEdgeCreationModeChange,
  pendingEdgeSource = null,
  onPendingEdgeSourceChange,
  onEdgeCreate,
  className,
}: GraphCanvasProps) {
  const [layoutDirection, setLayoutDirection] = useState<LayoutDirection>('TB')

  const initialNodes = useMemo(
    () => transformToReactFlowNodes(graphNodes, searchMatches, edgeCreationMode, pendingEdgeSource),
    [graphNodes, searchMatches, edgeCreationMode, pendingEdgeSource]
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

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const nodeId = Number(node.id)
      
      if (edgeCreationMode) {
        if (pendingEdgeSource === null) {
          onPendingEdgeSourceChange?.(nodeId)
        } else if (pendingEdgeSource !== nodeId) {
          onEdgeCreate?.(pendingEdgeSource, nodeId)
          onPendingEdgeSourceChange?.(null)
        }
        return
      }
      
      onNodeSelect?.(nodeId)
    },
    [edgeCreationMode, pendingEdgeSource, onNodeSelect, onPendingEdgeSourceChange, onEdgeCreate]
  )

  const handleNodeDoubleClick: NodeMouseHandler = useCallback(
    (_, node) => {
      onNodeDoubleClick?.(Number(node.id))
    },
    [onNodeDoubleClick]
  )

  const handlePaneClick = useCallback(() => {
    if (edgeCreationMode) {
      onPendingEdgeSourceChange?.(null)
      return
    }
    onNodeSelect?.(null)
  }, [edgeCreationMode, onNodeSelect, onPendingEdgeSourceChange])

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
        onNodeClick={handleNodeClick}
        onNodeDoubleClick={handleNodeDoubleClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        connectionLineType={ConnectionLineType.SmoothStep}
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
        />
        <Panel position="top-right" className="flex gap-1">
          <Button
            variant={edgeCreationMode ? 'default' : 'outline'}
            size="sm"
            onClick={() => {
              onEdgeCreationModeChange?.(!edgeCreationMode)
              onPendingEdgeSourceChange?.(null)
            }}
            className={edgeCreationMode ? 'bg-blue-600 hover:bg-blue-700' : ''}
          >
            <Link2 className="h-4 w-4 mr-1" />
            {edgeCreationMode ? 'Linking...' : 'Link'}
          </Button>
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
        </Panel>
        {edgeCreationMode && (
          <Panel position="top-center" className="flex items-center gap-3 bg-blue-600 text-white px-4 py-2.5 rounded-lg shadow-lg">
            <Link2 className="h-5 w-5" />
            <div className="flex flex-col">
              <span className="text-sm font-semibold">
                {pendingEdgeSource 
                  ? 'Step 2: Click the target node' 
                  : 'Step 1: Click the source node'}
              </span>
              <span className="text-xs opacity-80">
                {pendingEdgeSource 
                  ? 'Select where the connection should go' 
                  : 'Select where the connection starts from'}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 hover:bg-blue-700 text-white ml-2"
              onClick={() => {
                onEdgeCreationModeChange?.(false)
                onPendingEdgeSourceChange?.(null)
              }}
            >
              <X className="h-4 w-4" />
            </Button>
          </Panel>
        )}
      </ReactFlow>
    </div>
  )
}
