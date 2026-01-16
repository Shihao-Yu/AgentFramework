import { useState, useCallback, useMemo, useEffect } from 'react'
import { apiRequest } from '@/lib/api'
import type {
  KnowledgeNode,
  NodeType,
  NodeStatus,
  CreateNodeRequest,
  UpdateNodeRequest,
  NodeListResponse,
  NodeDetailResponse,
  KnowledgeEdge,
} from '@/types/graph'

interface NodeFilters {
  tenant_ids?: string[]
  node_types?: NodeType[]
  tags?: string[]
  status?: NodeStatus[]
  search?: string
  dataset_name?: string
  page?: number
  limit?: number
}

interface ApiNodeListResponse {
  data: KnowledgeNode[]
  total: number
  page: number
  limit: number
  total_pages: number
}

interface ApiNodeDetailResponse {
  id: number
  tenant_id: string
  node_type: NodeType
  title: string
  summary?: string
  content: Record<string, unknown>
  tags: string[]
  dataset_name?: string
  field_path?: string
  data_type?: string
  visibility: string
  status: string
  source?: string
  source_reference?: string
  version?: number
  created_by?: string
  created_at: string
  updated_by?: string
  updated_at?: string
  incoming_edges?: KnowledgeEdge[]
  outgoing_edges?: KnowledgeEdge[]
  edges_count?: number
}

interface NodeSearchResult {
  id: number
  tenant_id: string
  node_type: NodeType
  title: string
  summary?: string
  content: Record<string, unknown>
  tags: string[]
  dataset_name?: string
  field_path?: string
  bm25_rank?: number
  vector_rank?: number
  bm25_score?: number
  vector_score?: number
  rrf_score: number
}

interface NodeSearchResponse {
  results: NodeSearchResult[]
  total: number
  page: number
  limit: number
}

interface PaginationInfo {
  page: number
  limit: number
  total: number
  totalPages: number
}

const DEFAULT_LIMIT = 100

export function useNodes(initialFilters: NodeFilters = {}) {
  const [nodes, setNodes] = useState<KnowledgeNode[]>([])
  const [allTags, setAllTags] = useState<string[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<NodeFilters>({
    page: 1,
    limit: DEFAULT_LIMIT,
    ...initialFilters,
  })
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    limit: DEFAULT_LIMIT,
    total: 0,
    totalPages: 0,
  })

  const paginatedResponse = useMemo((): NodeListResponse => {
    return {
      items: nodes,
      total: pagination.total,
      page: pagination.page,
      pages: pagination.totalPages,
    }
  }, [nodes, pagination])

  const fetchNodes = useCallback(async (currentFilters?: NodeFilters) => {
    const f = currentFilters || filters
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | number | boolean | string[] | undefined> = {
        page: f.page || 1,
        limit: f.limit || DEFAULT_LIMIT,
      }
      
      if (f.tenant_ids && f.tenant_ids.length > 0) {
        params.tenant_ids = f.tenant_ids
      }
      if (f.node_types && f.node_types.length > 0) {
        params.node_types = f.node_types
      }
      if (f.tags && f.tags.length > 0) {
        params.tags = f.tags
      }
      if (f.status && f.status.length > 0) {
        params.status = f.status[0] // API takes single status
      }
      if (f.search && f.search.trim()) {
        params.search = f.search.trim()
      }
      if (f.dataset_name) {
        params.dataset_name = f.dataset_name
      }
      
      const response = await apiRequest<ApiNodeListResponse>('/api/nodes', { params })
      
      setNodes(response.data)
      setPagination({
        page: response.page,
        limit: response.limit,
        total: response.total,
        totalPages: response.total_pages,
      })
      
      // Collect all unique tags from results
      const tagsFromResults = new Set<string>()
      response.data.forEach(node => {
        node.tags.forEach(tag => tagsFromResults.add(tag))
      })
      setAllTags(prev => {
        const merged = new Set([...prev, ...tagsFromResults])
        return Array.from(merged).sort()
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch nodes'
      setError(message)
      console.error('Failed to fetch nodes:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters])

  // Fetch all tags on mount
  const fetchAllTags = useCallback(async () => {
    try {
      const params: Record<string, string | string[] | number> = {
        limit: 100,
      }
      if (filters.node_types && filters.node_types.length > 0) {
        params.node_types = filters.node_types
      }
      if (filters.tenant_ids && filters.tenant_ids.length > 0) {
        params.tenant_ids = filters.tenant_ids
      }
      const response = await apiRequest<ApiNodeListResponse>('/api/nodes', { params })
      const tags = new Set<string>()
      response.data.forEach(node => {
        node.tags.forEach(tag => tags.add(tag))
      })
      setAllTags(Array.from(tags).sort())
    } catch (err) {
      console.error('Failed to fetch tags:', err)
    }
  }, [filters.node_types, filters.tenant_ids])

  useEffect(() => {
    fetchNodes()
    fetchAllTags()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const getNode = useCallback(async (id: number): Promise<NodeDetailResponse | null> => {
    try {
      const response = await apiRequest<ApiNodeDetailResponse>(`/api/nodes/${id}`, {
        params: { include_edges: true },
      })
      
      const node: KnowledgeNode = {
        id: response.id,
        tenant_id: response.tenant_id,
        node_type: response.node_type,
        title: response.title,
        summary: response.summary,
        content: response.content as unknown as KnowledgeNode['content'],
        tags: response.tags,
        dataset_name: response.dataset_name,
        field_path: response.field_path,
        data_type: response.data_type,
        visibility: response.visibility as KnowledgeNode['visibility'],
        status: response.status as KnowledgeNode['status'],
        source: response.source,
        source_reference: response.source_reference,
        version: response.version,
        created_by: response.created_by,
        created_at: response.created_at,
        updated_by: response.updated_by,
        updated_at: response.updated_at,
      }
      
      return {
        node,
        edges: [...(response.incoming_edges || []), ...(response.outgoing_edges || [])],
      }
    } catch (err) {
      console.error(`Failed to fetch node ${id}:`, err)
      return null
    }
  }, [])

  const searchNodes = useCallback(async (
    query: string,
    options?: {
      node_types?: NodeType[]
      tags?: string[]
      bm25_weight?: number
      vector_weight?: number
      limit?: number
    }
  ): Promise<NodeSearchResult[]> => {
    try {
      const params: Record<string, string | number | string[] | undefined> = {
        q: query,
        limit: options?.limit || DEFAULT_LIMIT,
      }
      
      if (options?.node_types && options.node_types.length > 0) {
        params.node_types = options.node_types
      }
      if (options?.tags && options.tags.length > 0) {
        params.tags = options.tags
      }
      if (options?.bm25_weight !== undefined) {
        params.bm25_weight = options.bm25_weight
      }
      if (options?.vector_weight !== undefined) {
        params.vector_weight = options.vector_weight
      }
      
      const response = await apiRequest<NodeSearchResponse>('/api/nodes/search', { params })
      return response.results
    } catch (err) {
      console.error('Failed to search nodes:', err)
      return []
    }
  }, [])

  const createNode = useCallback(async (data: CreateNodeRequest): Promise<KnowledgeNode> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<KnowledgeNode>('/api/nodes', {
        method: 'POST',
        body: JSON.stringify(data),
      })
      
      // Refresh the list
      await fetchNodes()
      
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create node'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [fetchNodes])

  const updateNode = useCallback(async (id: number, data: UpdateNodeRequest): Promise<KnowledgeNode | null> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<KnowledgeNode>(`/api/nodes/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      })
      
      // Update local state
      setNodes(prev => prev.map(node => 
        node.id === id ? response : node
      ))
      
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update node'
      setError(message)
      console.error(`Failed to update node ${id}:`, err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteNode = useCallback(async (id: number): Promise<boolean> => {
    setIsLoading(true)
    setError(null)
    
    try {
      await apiRequest<{ success: boolean }>(`/api/nodes/${id}`, {
        method: 'DELETE',
      })
      
      setNodes(prev => prev.filter(node => node.id !== id))
      setPagination(prev => ({ ...prev, total: prev.total - 1 }))
      
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete node'
      setError(message)
      console.error(`Failed to delete node ${id}:`, err)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [])

  const updateFilters = useCallback((newFilters: Partial<NodeFilters>) => {
    setFilters(prev => {
      const updated = { ...prev, ...newFilters }
      // Reset to page 1 when search or tags change
      if (newFilters.search !== undefined || newFilters.tags !== undefined) {
        updated.page = 1
      }
      fetchNodes(updated)
      return updated
    })
  }, [fetchNodes])

  return {
    nodes,
    allTags,
    pagination,
    response: paginatedResponse,
    isLoading,
    error,
    filters,
    getNode,
    searchNodes,
    createNode,
    updateNode,
    deleteNode,
    updateFilters,
    fetchNodes,
  }
}

export function useNodesByType(nodeType: NodeType, tenantIds: string[] = []) {
  const { 
    nodes, 
    allTags,
    pagination,
    isLoading, 
    error, 
    filters,
    createNode, 
    updateNode, 
    deleteNode, 
    updateFilters,
    fetchNodes 
  } = useNodes({
    node_types: [nodeType],
    tenant_ids: tenantIds.length > 0 ? tenantIds : undefined,
    limit: DEFAULT_LIMIT,
  })

  // Fetch on mount and when dependencies change
  const refetch = useCallback(() => {
    fetchNodes({
      ...filters,
      node_types: [nodeType],
      tenant_ids: tenantIds.length > 0 ? tenantIds : undefined,
    })
  }, [fetchNodes, nodeType, tenantIds, filters])

  return {
    nodes,
    allTags,
    pagination,
    filters,
    isLoading,
    error,
    createNode,
    updateNode,
    deleteNode,
    updateFilters,
    refetch,
  }
}
