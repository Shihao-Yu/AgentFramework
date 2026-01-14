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
  onEdgeCreate?: (sourceId: number, targetId: number) => void
  className?: string
}

function transformToReactFlowNodes(
  graphNodes: GraphNode[],
  searchMatches: number[] = []
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
  onEdgeCreate,
  className,
}: GraphCanvasProps) {
  const [layoutDirection, setLayoutDirection] = useState<LayoutDirection>('TB')

  const initialNodes = useMemo(
    () => transformToReactFlowNodes(graphNodes, searchMatches),
    [graphNodes, searchMatches]
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
        />
        <Panel position="top-right" className="flex gap-1">
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
      </ReactFlow>
    </div>
  )
}
