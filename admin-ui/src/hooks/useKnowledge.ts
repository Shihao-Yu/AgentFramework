import { useState, useMemo, useCallback, useEffect } from 'react'
import { apiRequest } from '@/lib/api'
import type {
  LegacyKnowledgeItem,
  KnowledgeCategory,
  KnowledgeVariant,
  KnowledgeRelationship,
} from '@/types/knowledge'

interface LegacyKnowledgeFilters {
  search?: string
  knowledge_type?: string[]
  tags?: string[]
  category_id?: number
  status?: string[]
}

interface LegacyFAQFormData {
  knowledge_type?: string
  category_id?: number
  title: string
  summary?: string
  answer: string
  tags: string[]
  visibility: string
  status: string
}

interface FAQContent {
  answer: string
}

interface DuplicateCheckResult {
  item: LegacyKnowledgeItem
  similarity: number
  match_type: 'exact' | 'high' | 'medium'
}

interface NodeListResponse {
  data: Array<{
    id: number
    tenant_id: string
    node_type: string
    title: string
    summary?: string
    content: Record<string, unknown>
    tags: string[]
    visibility: string
    status: string
    created_by?: string
    created_at: string
    updated_at?: string
  }>
  total: number
  page: number
  limit: number
}

interface SearchResponse {
  results: Array<{
    node: {
      id: number
      title: string
      summary?: string
      content: Record<string, unknown>
      tags: string[]
    }
    rrf_score: number
  }>
}

export function useKnowledgeItems(filters: LegacyKnowledgeFilters = {}) {
  const [items, setItems] = useState<LegacyKnowledgeItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchItems = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string> = { limit: '100' }
      if (filters.search) params.search = filters.search
      if (filters.knowledge_type?.length) params.node_types = filters.knowledge_type.join(',')
      if (filters.tags?.length) params.tags = filters.tags.join(',')
      if (filters.status?.length) params.status = filters.status[0]

      const response = await apiRequest<NodeListResponse>('/api/nodes', { params })
      
      const mappedItems: LegacyKnowledgeItem[] = response.data.map(node => ({
        id: node.id,
        knowledge_type: node.node_type,
        title: node.title,
        summary: node.summary,
        content: node.content,
        tags: node.tags,
        visibility: node.visibility,
        status: node.status,
        created_by: node.created_by,
        created_at: node.created_at,
        updated_at: node.updated_at,
        variants_count: 0,
        relationships_count: 0,
        hits_count: 0,
      }))
      
      setItems(mappedItems)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch items'
      setError(message)
      console.error('Failed to fetch knowledge items:', err)
    } finally {
      setIsLoading(false)
    }
  }, [filters.search, filters.knowledge_type, filters.tags, filters.status])

  useEffect(() => {
    fetchItems()
  }, [fetchItems])

  const filteredItems = useMemo(() => {
    let result = [...items]

    if (filters.category_id) {
      result = result.filter((item) => item.category_id === filters.category_id)
    }

    return result
  }, [items, filters.category_id])

  const createItem = useCallback(async (data: LegacyFAQFormData): Promise<LegacyKnowledgeItem> => {
    setIsLoading(true)
    
    try {
      const response = await apiRequest<{ id: number }>('/api/nodes', {
        method: 'POST',
        body: JSON.stringify({
          tenant_id: 'default',
          node_type: data.knowledge_type || 'faq',
          title: data.title,
          summary: data.summary,
          content: {
            answer: data.answer,
          },
          tags: data.tags,
          visibility: data.visibility,
          status: data.status,
        }),
      })

      const newItem: LegacyKnowledgeItem = {
        id: response.id,
        knowledge_type: data.knowledge_type || 'faq',
        category_id: data.category_id,
        title: data.title,
        summary: data.summary,
        content: {
          answer: data.answer,
        },
        tags: data.tags,
        visibility: data.visibility,
        status: data.status,
        created_by: 'current-user',
        created_at: new Date().toISOString(),
        variants_count: 0,
        relationships_count: 0,
        hits_count: 0,
      }

      setItems((prev) => [...prev, newItem])
      return newItem
    } finally {
      setIsLoading(false)
    }
  }, [])

  const updateItem = useCallback(async (id: number, data: Partial<LegacyFAQFormData>): Promise<LegacyKnowledgeItem> => {
    setIsLoading(true)
    
    try {
      const updatePayload: Record<string, unknown> = {}
      if (data.title) updatePayload.title = data.title
      if (data.tags) updatePayload.tags = data.tags
      if (data.visibility) updatePayload.visibility = data.visibility
      if (data.status) updatePayload.status = data.status
      if (data.answer) {
        updatePayload.content = {
          answer: data.answer,
        }
      }

      await apiRequest(`/api/nodes/${id}`, {
        method: 'PUT',
        body: JSON.stringify(updatePayload),
      })

      let updatedItem: LegacyKnowledgeItem | undefined

      setItems((prev) =>
        prev.map((item): LegacyKnowledgeItem => {
          if (item.id === id) {
            updatedItem = {
              ...item,
              title: data.title ?? item.title,
              tags: data.tags ?? item.tags,
              visibility: data.visibility ?? item.visibility,
              status: data.status ?? item.status,
              content: data.answer
                ? { answer: data.answer }
                : item.content,
              updated_at: new Date().toISOString(),
            }
            return updatedItem
          }
          return item
        })
      )

      return updatedItem!
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteItem = useCallback(async (id: number): Promise<void> => {
    setIsLoading(true)
    
    try {
      await apiRequest(`/api/nodes/${id}`, { method: 'DELETE' })
      setItems((prev) => prev.filter((item) => item.id !== id))
    } finally {
      setIsLoading(false)
    }
  }, [])

  const getItem = useCallback((id: number): LegacyKnowledgeItem | undefined => {
    return items.find((item) => item.id === id)
  }, [items])

  return {
    items: filteredItems,
    allItems: items,
    isLoading,
    error,
    createItem,
    updateItem,
    deleteItem,
    getItem,
    refetch: fetchItems,
  }
}

export function useDuplicateCheck() {
  const [isChecking, setIsChecking] = useState(false)
  const [duplicates, setDuplicates] = useState<DuplicateCheckResult[]>([])

  const checkDuplicates = useCallback(async (text: string): Promise<DuplicateCheckResult[]> => {
    if (!text || text.length < 10) {
      setDuplicates([])
      return []
    }

    setIsChecking(true)

    try {
      const response = await apiRequest<SearchResponse>('/api/search', {
        method: 'POST',
        body: JSON.stringify({ query: text, limit: 5 }),
      })

      const results: DuplicateCheckResult[] = response.results
        .filter(r => r.rrf_score >= 0.5)
        .map(r => ({
          item: {
            id: r.node.id,
            knowledge_type: 'faq',
            title: r.node.title,
            summary: r.node.summary,
            content: r.node.content,
            tags: r.node.tags,
            visibility: 'internal',
            status: 'published',
            created_at: new Date().toISOString(),
            variants_count: 0,
            relationships_count: 0,
            hits_count: 0,
          },
          similarity: r.rrf_score,
          match_type: r.rrf_score >= 0.9 ? 'exact' : r.rrf_score >= 0.7 ? 'high' : 'medium',
        }))

      setDuplicates(results)
      return results
    } catch {
      setDuplicates([])
      return []
    } finally {
      setIsChecking(false)
    }
  }, [])

  const clearDuplicates = useCallback(() => {
    setDuplicates([])
  }, [])

  return {
    duplicates,
    isChecking,
    checkDuplicates,
    clearDuplicates,
  }
}

export function useCategories() {
  const [categories, setCategories] = useState<KnowledgeCategory[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchCategories = async () => {
      try {
        const response = await apiRequest<{ categories: KnowledgeCategory[] }>('/api/categories')
        setCategories(response.categories || [])
      } catch {
        setCategories([])
      } finally {
        setIsLoading(false)
      }
    }
    fetchCategories()
  }, [])

  const getCategoryTree = useMemo(() => {
    const rootCategories = categories.filter((c) => !c.parent_id)
    const getChildren = (parentId: number): KnowledgeCategory[] => {
      return categories.filter((c) => c.parent_id === parentId)
    }

    return { rootCategories, getChildren }
  }, [categories])

  return {
    categories,
    isLoading,
    ...getCategoryTree,
  }
}

export function useVariants(knowledgeItemId: number) {
  const [variants, setVariants] = useState<KnowledgeVariant[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchVariants = async () => {
      try {
        const response = await apiRequest<{ variants: KnowledgeVariant[] }>(`/api/nodes/${knowledgeItemId}/variants`)
        setVariants(response.variants || [])
      } catch {
        setVariants([])
      } finally {
        setIsLoading(false)
      }
    }
    fetchVariants()
  }, [knowledgeItemId])

  const addVariant = useCallback(async (text: string): Promise<KnowledgeVariant> => {
    setIsLoading(true)
    
    try {
      const response = await apiRequest<{ id: number }>(`/api/nodes/${knowledgeItemId}/variants`, {
        method: 'POST',
        body: JSON.stringify({ variant_text: text }),
      })

      const newVariant: KnowledgeVariant = {
        id: response.id,
        knowledge_item_id: knowledgeItemId,
        variant_text: text,
        source: 'manual',
        created_by: 'current-user',
        created_at: new Date().toISOString(),
      }

      setVariants((prev) => [...prev, newVariant])
      return newVariant
    } finally {
      setIsLoading(false)
    }
  }, [knowledgeItemId])

  const deleteVariant = useCallback(async (variantId: number): Promise<void> => {
    setIsLoading(true)
    
    try {
      await apiRequest(`/api/nodes/${knowledgeItemId}/variants/${variantId}`, { method: 'DELETE' })
      setVariants((prev) => prev.filter((v) => v.id !== variantId))
    } finally {
      setIsLoading(false)
    }
  }, [knowledgeItemId])

  return {
    variants,
    isLoading,
    addVariant,
    deleteVariant,
  }
}

export function useRelationships(knowledgeItemId: number) {
  const [relationships, setRelationships] = useState<KnowledgeRelationship[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchRelationships = async () => {
      try {
        const response = await apiRequest<{ edges: KnowledgeRelationship[] }>(`/api/nodes/${knowledgeItemId}/edges`)
        setRelationships(response.edges || [])
      } catch {
        setRelationships([])
      } finally {
        setIsLoading(false)
      }
    }
    fetchRelationships()
  }, [knowledgeItemId])

  const populatedRelationships = useMemo(() => {
    return relationships
  }, [relationships])

  const addRelationship = useCallback(
    async (
      targetId: number,
      relationshipType: string,
      isBidirectional: boolean = false
    ): Promise<KnowledgeRelationship> => {
      setIsLoading(true)
      
      try {
        const response = await apiRequest<{ id: number }>('/api/edges', {
          method: 'POST',
          body: JSON.stringify({
            source_id: knowledgeItemId,
            target_id: targetId,
            edge_type: relationshipType,
            is_bidirectional: isBidirectional,
          }),
        })

        const newRel: KnowledgeRelationship = {
          id: response.id,
          source_id: knowledgeItemId,
          target_id: targetId,
          relationship_type: relationshipType as KnowledgeRelationship['relationship_type'],
          weight: 1.0,
          is_bidirectional: isBidirectional,
          is_auto_generated: false,
          created_by: 'current-user',
          created_at: new Date().toISOString(),
        }

        setRelationships((prev) => [...prev, newRel])
        return newRel
      } finally {
        setIsLoading(false)
      }
    },
    [knowledgeItemId]
  )

  const deleteRelationship = useCallback(async (relationshipId: number): Promise<void> => {
    setIsLoading(true)
    
    try {
      await apiRequest(`/api/edges/${relationshipId}`, { method: 'DELETE' })
      setRelationships((prev) => prev.filter((r) => r.id !== relationshipId))
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    relationships: populatedRelationships,
    isLoading,
    addRelationship,
    deleteRelationship,
  }
}

export function useTags() {
  const [tags, setTags] = useState<string[]>([])
  const [popularTags, setPopularTags] = useState<Array<{ tag: string; count: number }>>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchTags = async () => {
      try {
        const response = await apiRequest<{ tags: Array<{ tag: string; item_count: number }> }>('/api/metrics/tags', {
          params: { limit: '50' },
        })
        
        const tagList = response.tags?.map(t => t.tag) || []
        const popular = response.tags?.map(t => ({ tag: t.tag, count: t.item_count })).slice(0, 10) || []
        
        setTags(tagList)
        setPopularTags(popular)
      } catch {
        setTags([])
        setPopularTags([])
      } finally {
        setIsLoading(false)
      }
    }
    fetchTags()
  }, [])

  return {
    tags,
    popularTags,
    isLoading,
  }
}
