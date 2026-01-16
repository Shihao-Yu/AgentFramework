import dagre from '@dagrejs/dagre'
import type { Node, Edge } from '@xyflow/react'

export type LayoutDirection = 'TB' | 'LR' | 'BT' | 'RL'

interface LayoutOptions {
  direction?: LayoutDirection
  nodeWidth?: number
  nodeHeight?: number
  rankSep?: number
  nodeSep?: number
}

export function getLayoutedElements<N extends Node, E extends Edge>(
  nodes: N[],
  edges: E[],
  options: LayoutOptions = {}
): { nodes: N[]; edges: E[] } {
  const {
    direction = 'TB',
    nodeWidth = 200,
    nodeHeight = 80,
    rankSep = 80,
    nodeSep = 50,
  } = options

  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const isHorizontal = direction === 'LR' || direction === 'RL'
  dagreGraph.setGraph({
    rankdir: direction,
    ranksep: rankSep,
    nodesep: nodeSep,
  })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    
    return {
      ...node,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    } as N
  })

  return { nodes: layoutedNodes, edges }
}

export function getRadialLayout<N extends Node>(
  nodes: N[],
  centerId: string,
  radius: number = 200
): N[] {
  const centerNode = nodes.find(n => n.id === centerId)
  const otherNodes = nodes.filter(n => n.id !== centerId)

  if (!centerNode) return nodes

  const angleStep = (2 * Math.PI) / otherNodes.length

  const layoutedNodes = [
    {
      ...centerNode,
      position: { x: 400, y: 300 },
    },
    ...otherNodes.map((node, index) => ({
      ...node,
      position: {
        x: 400 + radius * Math.cos(angleStep * index - Math.PI / 2),
        y: 300 + radius * Math.sin(angleStep * index - Math.PI / 2),
      },
    })),
  ]

  return layoutedNodes as N[]
}

export function getGridLayout<N extends Node>(
  nodes: N[],
  options: { columns?: number; cellWidth?: number; cellHeight?: number; padding?: number } = {}
): N[] {
  const {
    columns = 4,
    cellWidth = 250,
    cellHeight = 150,
    padding = 50,
  } = options

  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: padding + (index % columns) * cellWidth,
      y: padding + Math.floor(index / columns) * cellHeight,
    },
  })) as N[]
}
