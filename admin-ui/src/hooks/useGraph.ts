import { useState, useCallback, useMemo } from 'react'
import { apiRequest } from '@/lib/api'
import type {
  GraphNode,
  GraphEdge,
  GraphSearchRequest,
  GraphSearchResponse,
  GraphExpandResponse,
  GraphStatsResponse,
  NodeType,
  EdgeType,
  KnowledgeNode,
} from '@/types/graph'

interface NeighborResponse {
  id: number
  depth: number
  tenant_id: string
  node_type: string
  title: string
  tags: string[]
  dataset_name?: string
  field_path?: string
}

interface ApiGraphStatsResponse {
  node_count: number
  edge_count: number
  density: number
  connected_components: number
  avg_degree: number
  orphan_nodes: number
  node_types: Record<string, number>
  edge_types: Record<string, number>
  last_sync?: string
}

interface ContextRequest {
  query: string
  tenant_ids: string[]
  entry_types?: NodeType[]
  entry_limit?: number
  expand?: boolean
  expansion_types?: NodeType[]
  max_depth?: number
  context_limit?: number
  include_entities?: boolean
  include_schemas?: boolean
  include_examples?: boolean
}

interface ContextNode {
  id: number
  node_type: NodeType
  title: string
  summary?: string
  content: Record<string, unknown>
  tags: string[]
  score: number
  distance?: number
  path?: number[]
  edge_type?: EdgeType
  match_source?: 'bm25' | 'vector' | 'hybrid'
}

interface ContextResponse {
  entry_points: ContextNode[]
  context: ContextNode[]
  entities?: Array<{
    id: number
    title: string
    entity_path: string
    related_schemas: string[]
  }>
  stats: {
    nodes_searched: number
    nodes_expanded: number
    max_depth_reached: number
  }
}

export function useGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [searchMatches, setSearchMatches] = useState<number[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)

  const selectedNode = useMemo(() => {
    if (!selectedNodeId) return null
    return nodes.find(n => n.id === selectedNodeId) || null
  }, [nodes, selectedNodeId])

  const search = useCallback(async (request: GraphSearchRequest): Promise<GraphSearchResponse> => {
    setIsLoading(true)
    setError(null)

    try {
      // If no query, load nodes directly from /api/nodes
      if (!request.query || !request.query.trim()) {
        const params: Record<string, string | number | string[] | undefined> = {
          limit: request.limit || 100,
          page: 1,
        }
        if (request.tenant_ids && request.tenant_ids.length > 0) {
          params.tenant_ids = request.tenant_ids
        }
        if (request.node_types && request.node_types.length > 0) {
          params.node_types = request.node_types
        }

        const nodesResponse = await apiRequest<{ data: KnowledgeNode[]; total: number }>(
          '/api/nodes',
          { params }
        )

        const graphNodes: GraphNode[] = (nodesResponse.data ?? []).map(n => ({
          id: n.id,
          tenant_id: n.tenant_id,
          node_type: n.node_type as NodeType,
          title: n.title,
          summary: n.summary,
          content: n.content,
          tags: n.tags,
          visibility: n.visibility,
          status: n.status,
          created_at: n.created_at,
        }))

        // Fetch edges for all loaded nodes
        const nodeIds = graphNodes.map(n => n.id)
        const graphEdges: GraphEdge[] = []
        
        if (nodeIds.length > 0) {
          const edgesResponse = await apiRequest<{ edges: Array<{ id: number; source_id: number; target_id: number; edge_type: EdgeType; weight: number }> }>(
            '/api/edges',
            { params: { limit: 500 } }
          )
          
          const nodeIdSet = new Set(nodeIds)
          ;(edgesResponse.edges ?? []).forEach(edge => {
            if (nodeIdSet.has(edge.source_id) && nodeIdSet.has(edge.target_id)) {
              graphEdges.push({
                source: edge.source_id,
                target: edge.target_id,
                edge_type: edge.edge_type,
                weight: edge.weight,
              })
            }
          })
        }

        setNodes(graphNodes)
        setEdges(graphEdges)
        setSearchMatches([])

        const byType: Partial<Record<NodeType, number>> = {}
        graphNodes.forEach(n => {
          byType[n.node_type] = (byType[n.node_type] || 0) + 1
        })

        return {
          nodes: graphNodes,
          edges: graphEdges,
          search_matches: [],
          stats: {
            total_nodes: graphNodes.length,
            by_type: byType,
          },
        }
      }

      // Use the context API for search with graph expansion
      const contextRequest: ContextRequest = {
        query: request.query || '',
        tenant_ids: request.tenant_ids,
        entry_types: request.node_types,
        entry_limit: request.limit || 10,
        expand: true,
        max_depth: request.depth || 2,
        context_limit: request.limit || 50,
        include_entities: true,
        include_schemas: true,
        include_examples: true,
      }

      const response = await apiRequest<ContextResponse>('/api/context', {
        method: 'POST',
        body: JSON.stringify(contextRequest),
      })

      // Convert context response to graph nodes
      const allContextNodes = [...(response.entry_points ?? []), ...(response.context ?? [])]
      const nodeMap = new Map<number, GraphNode>()
      
      allContextNodes.forEach(cn => {
        if (!nodeMap.has(cn.id)) {
          nodeMap.set(cn.id, {
            id: cn.id,
            tenant_id: '', // Will be populated if available
            node_type: cn.node_type,
            title: cn.title,
            summary: cn.summary,
            content: cn.content as unknown as KnowledgeNode['content'],
            tags: cn.tags,
            visibility: 'internal',
            status: 'published',
            created_at: new Date().toISOString(),
          })
        }
      })

      const graphNodes = Array.from(nodeMap.values())
      const matchedIds = (response.entry_points ?? []).map(ep => ep.id)

      const nodeIds = graphNodes.map(n => n.id)
      const graphEdges: GraphEdge[] = []
      
      if (nodeIds.length > 0) {
        const edgePromises = nodeIds.map(nodeId =>
          apiRequest<{ edges: Array<{ id: number; source_id: number; target_id: number; edge_type: EdgeType; weight: number }> }>('/api/edges', {
            params: { node_id: nodeId, limit: 100 },
          }).catch(() => ({ edges: [] }))
        )
        
        const edgeResponses = await Promise.all(edgePromises)
        const seenEdges = new Set<string>()
        const nodeIdSet = new Set(nodeIds)
        
        edgeResponses.forEach(response => {
          ;(response.edges ?? []).forEach(edge => {
            if (nodeIdSet.has(edge.source_id) && nodeIdSet.has(edge.target_id)) {
              const edgeKey = `${edge.source_id}-${edge.target_id}`
              if (!seenEdges.has(edgeKey)) {
                seenEdges.add(edgeKey)
                graphEdges.push({
                  source: edge.source_id,
                  target: edge.target_id,
                  edge_type: edge.edge_type,
                  weight: edge.weight,
                })
              }
            }
          })
        })
      }

      // Filter implicit edges if requested
      let finalEdges = graphEdges
      if (!request.include_implicit) {
        finalEdges = graphEdges.filter(
          e => e.edge_type !== 'shared_tag' && e.edge_type !== 'similar'
        )
      }

      setNodes(graphNodes)
      setEdges(finalEdges)
      setSearchMatches(matchedIds)

      const byType: Partial<Record<NodeType, number>> = {}
      graphNodes.forEach(n => {
        byType[n.node_type] = (byType[n.node_type] || 0) + 1
      })

      return {
        nodes: graphNodes,
        edges: finalEdges,
        search_matches: matchedIds,
        stats: {
          total_nodes: graphNodes.length,
          by_type: byType,
        },
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to search graph'
      setError(message)
      console.error('Failed to search graph:', err)
      
      return {
        nodes: [],
        edges: [],
        search_matches: [],
        stats: { total_nodes: 0, by_type: {} },
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  const expand = useCallback(async (
    nodeId: number,
    depth: number = 1,
    nodeTypes?: NodeType[],
    edgeTypes?: EdgeType[]
  ): Promise<GraphExpandResponse> => {
    setIsLoading(true)
    setError(null)

    try {
      const params: Record<string, string | number | string[] | undefined> = {
        depth,
      }
      if (edgeTypes && edgeTypes.length > 0) {
        params.edge_types = edgeTypes
      }

      const neighbors = await apiRequest<NeighborResponse[]>(
        `/api/graph/neighbors/${nodeId}`,
        { params }
      )

      // Get the center node
      const centerNodeResponse = await apiRequest<KnowledgeNode>(`/api/nodes/${nodeId}`)
      
      const centerNode: GraphNode = {
        ...centerNodeResponse,
        x: 400,
        y: 300,
      }

      // Convert neighbors to graph nodes
      const graphNodes: GraphNode[] = (neighbors ?? [])
        .filter(n => !nodeTypes || nodeTypes.includes(n.node_type as NodeType))
        .map(n => ({
          id: n.id,
          tenant_id: n.tenant_id,
          node_type: n.node_type as NodeType,
          title: n.title,
          tags: n.tags,
          dataset_name: n.dataset_name,
          field_path: n.field_path,
          content: {} as KnowledgeNode['content'],
          visibility: 'internal' as const,
          status: 'published' as const,
          created_at: new Date().toISOString(),
        }))

      // Add center node if not already included
      if (!graphNodes.some(n => n.id === nodeId)) {
        graphNodes.unshift(centerNode)
      }

      // Build edges (we need to fetch them separately or infer from neighbors)
      // For now, create edges from center to all neighbors
      const graphEdges: GraphEdge[] = (neighbors ?? []).map(n => ({
        source: nodeId,
        target: n.id,
        edge_type: 'related' as EdgeType,
        weight: 1.0,
      }))

      setNodes(graphNodes)
      setEdges(graphEdges)

      return {
        center_node: centerNode,
        nodes: graphNodes,
        edges: graphEdges,
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to expand node'
      setError(message)
      console.error('Failed to expand node:', err)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const getStats = useCallback(async (_tenantIds?: string[]): Promise<GraphStatsResponse> => {
    try {
      const response = await apiRequest<ApiGraphStatsResponse>('/api/graph/stats')

      return {
        total_nodes: response.node_count,
        by_type: response.node_types as Partial<Record<NodeType, number>>,
        total_edges: response.edge_count,
        by_edge_type: response.edge_types as Partial<Record<EdgeType, number>>,
        orphan_nodes: response.orphan_nodes,
        avg_connections: response.avg_degree,
      }
    } catch (err) {
      console.error('Failed to fetch graph stats:', err)
      return {
        total_nodes: 0,
        by_type: {},
        total_edges: 0,
        by_edge_type: {},
        orphan_nodes: 0,
        avg_connections: 0,
      }
    }
  }, [])

  const getSuggestions = useCallback(async (nodeId: number, limit: number = 5) => {
    try {
      const response = await apiRequest<Array<{
        id: number
        score: number
        reason: string
        tenant_id: string
        node_type: string
        title: string
        tags: string[]
        dataset_name?: string
      }>>(`/api/graph/suggestions/${nodeId}`, {
        params: { limit },
      })
      
      return response
    } catch (err) {
      console.error('Failed to fetch suggestions:', err)
      return []
    }
  }, [])

  const findPaths = useCallback(async (sourceId: number, targetId: number, maxDepth: number = 5) => {
    try {
      const response = await apiRequest<{ paths: number[][] }>('/api/graph/paths', {
        params: { source_id: sourceId, target_id: targetId, max_depth: maxDepth },
      })
      
      return response.paths ?? []
    } catch (err) {
      console.error('Failed to find paths:', err)
      return []
    }
  }, [])

  const reloadGraph = useCallback(async () => {
    try {
      const response = await apiRequest<{ status: string; stats: ApiGraphStatsResponse }>(
        '/api/graph/reload',
        { method: 'POST' }
      )
      return response
    } catch (err) {
      console.error('Failed to reload graph:', err)
      throw err
    }
  }, [])

  const selectNode = useCallback((nodeId: number | null) => {
    setSelectedNodeId(nodeId)
  }, [])

  const clearGraph = useCallback(() => {
    setNodes([])
    setEdges([])
    setSearchMatches([])
    setSelectedNodeId(null)
    setError(null)
  }, [])

  return {
    nodes,
    edges,
    searchMatches,
    selectedNode,
    isLoading,
    error,
    search,
    expand,
    getStats,
    getSuggestions,
    findPaths,
    reloadGraph,
    selectNode,
    clearGraph,
  }
}
