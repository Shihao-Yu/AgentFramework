import { useState, useCallback } from 'react'
import { apiRequest } from '@/lib/api'
import type {
  KnowledgeEdge,
  EdgeType,
  CreateEdgeRequest,
  BulkCreateEdgesResponse,
} from '@/types/graph'

interface EdgeListResponse {
  edges: KnowledgeEdge[]
  total: number
  page: number
  limit: number
}

export function useEdges(nodeIds?: number[]) {
  const [edges, setEdges] = useState<KnowledgeEdge[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchEdges = useCallback(async (options?: {
    node_id?: number
    edge_types?: EdgeType[]
    include_auto_generated?: boolean
    direction?: 'incoming' | 'outgoing' | 'both'
  }) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | number | boolean | string[] | undefined> = {
        limit: 200,
      }
      
      if (options?.node_id) {
        params.node_id = options.node_id
      } else if (nodeIds && nodeIds.length > 0) {
        // Fetch edges for first node if multiple provided
        params.node_id = nodeIds[0]
      }
      
      if (options?.edge_types && options.edge_types.length > 0) {
        params.edge_types = options.edge_types
      }
      if (options?.include_auto_generated !== undefined) {
        params.include_auto_generated = options.include_auto_generated
      }
      if (options?.direction) {
        params.direction = options.direction
      }
      
      const response = await apiRequest<EdgeListResponse>('/api/edges', { params })
      setEdges(response.edges)
      return response.edges
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch edges'
      setError(message)
      console.error('Failed to fetch edges:', err)
      return []
    } finally {
      setIsLoading(false)
    }
  }, [nodeIds])

  const getEdgesForNode = useCallback((nodeId: number): KnowledgeEdge[] => {
    return edges.filter(
      edge => edge.source_id === nodeId || edge.target_id === nodeId
    )
  }, [edges])

  const createEdge = useCallback(async (data: CreateEdgeRequest): Promise<KnowledgeEdge> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<KnowledgeEdge>('/api/edges', {
        method: 'POST',
        body: JSON.stringify(data),
      })
      
      setEdges(prev => [...prev, response])
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create edge'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const createEdgesBulk = useCallback(async (
    edgeRequests: CreateEdgeRequest[]
  ): Promise<BulkCreateEdgesResponse> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<KnowledgeEdge[]>('/api/edges/bulk', {
        method: 'POST',
        body: JSON.stringify({ edges: edgeRequests }),
      })
      
      setEdges(prev => [...prev, ...response])
      
      return {
        created: response.length,
        errors: [],
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create edges'
      setError(message)
      
      return {
        created: 0,
        errors: [{ index: 0, error: message }],
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteEdge = useCallback(async (id: number): Promise<boolean> => {
    setIsLoading(true)
    setError(null)
    
    try {
      await apiRequest<{ success: boolean }>(`/api/edges/${id}`, {
        method: 'DELETE',
      })
      
      setEdges(prev => prev.filter(edge => edge.id !== id))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete edge'
      setError(message)
      console.error(`Failed to delete edge ${id}:`, err)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteEdgeByNodes = useCallback(async (
    sourceId: number,
    targetId: number,
    edgeType?: EdgeType
  ): Promise<boolean> => {
    // Find the edge first
    const edge = edges.find(e => {
      if (e.source_id !== sourceId || e.target_id !== targetId) return false
      if (edgeType && e.edge_type !== edgeType) return false
      return true
    })
    
    if (!edge) {
      console.error('Edge not found for deletion')
      return false
    }
    
    return deleteEdge(edge.id)
  }, [edges, deleteEdge])

  return {
    edges,
    isLoading,
    error,
    fetchEdges,
    getEdgesForNode,
    createEdge,
    createEdgesBulk,
    deleteEdge,
    deleteEdgeByNodes,
  }
}
