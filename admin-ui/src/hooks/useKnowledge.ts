import { useState, useMemo, useCallback } from 'react'
import {
  mockKnowledgeItems,
  mockCategories,
  mockVariants,
  mockRelationships,
  mockAllTags,
} from '@/data/mock-data'
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
  question: string
  answer: string
  tags: string[]
  visibility: string
  status: string
}

interface FAQContent {
  question: string
  answer: string
}

interface DuplicateCheckResult {
  item: LegacyKnowledgeItem
  similarity: number
  match_type: 'exact' | 'high' | 'medium'
}

// Simulate API delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// ==================== Knowledge Items Hook ====================

export function useKnowledgeItems(filters: LegacyKnowledgeFilters = {}) {
  const [items, setItems] = useState<LegacyKnowledgeItem[]>(mockKnowledgeItems)
  const [isLoading, setIsLoading] = useState(false)

  const filteredItems = useMemo(() => {
    let result = [...items]

    // Search filter
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(searchLower) ||
          item.summary?.toLowerCase().includes(searchLower) ||
          item.tags.some((tag) => tag.toLowerCase().includes(searchLower))
      )
    }

    // Type filter
    if (filters.knowledge_type && filters.knowledge_type.length > 0) {
      result = result.filter((item) => filters.knowledge_type!.includes(item.knowledge_type))
    }

    // Tags filter
    if (filters.tags && filters.tags.length > 0) {
      result = result.filter((item) => filters.tags!.some((tag) => item.tags.includes(tag)))
    }

    // Category filter
    if (filters.category_id) {
      result = result.filter((item) => item.category_id === filters.category_id)
    }

    // Status filter
    if (filters.status && filters.status.length > 0) {
      result = result.filter((item) => filters.status!.includes(item.status))
    }

    return result
  }, [items, filters])

  const createItem = useCallback(async (data: LegacyFAQFormData): Promise<LegacyKnowledgeItem> => {
    setIsLoading(true)
    await delay(500)

    const newItem: LegacyKnowledgeItem = {
      id: Math.max(...items.map((i) => i.id)) + 1,
      knowledge_type: data.knowledge_type || 'faq',
      category_id: data.category_id,
      category: mockCategories.find((c) => c.id === data.category_id),
      title: data.title,
      summary: data.summary,
      content: {
        question: data.question,
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
    setIsLoading(false)
    return newItem
  }, [items])

  const updateItem = useCallback(async (id: number, data: Partial<LegacyFAQFormData>): Promise<LegacyKnowledgeItem> => {
    setIsLoading(true)
    await delay(500)

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
            content: data.question && data.answer
              ? { question: data.question, answer: data.answer }
              : item.content,
            updated_at: new Date().toISOString(),
          }
          return updatedItem
        }
        return item
      })
    )

    setIsLoading(false)
    return updatedItem!
  }, [])

  const deleteItem = useCallback(async (id: number): Promise<void> => {
    setIsLoading(true)
    await delay(300)
    setItems((prev) => prev.filter((item) => item.id !== id))
    setIsLoading(false)
  }, [])

  const getItem = useCallback((id: number): LegacyKnowledgeItem | undefined => {
    return items.find((item) => item.id === id)
  }, [items])

  return {
    items: filteredItems,
    allItems: items,
    isLoading,
    createItem,
    updateItem,
    deleteItem,
    getItem,
  }
}

// ==================== Duplicate Check Hook ====================

export function useDuplicateCheck() {
  const [isChecking, setIsChecking] = useState(false)
  const [duplicates, setDuplicates] = useState<DuplicateCheckResult[]>([])

  const checkDuplicates = useCallback(async (text: string): Promise<DuplicateCheckResult[]> => {
    if (!text || text.length < 10) {
      setDuplicates([])
      return []
    }

    setIsChecking(true)
    await delay(300) // Simulate API call

    const textLower = text.toLowerCase()
    const words = textLower.split(/\s+/).filter((w) => w.length > 3)

    const results: DuplicateCheckResult[] = []

    for (const item of mockKnowledgeItems) {
      const titleLower = item.title.toLowerCase()
      const content = item.content as unknown as FAQContent
      const questionLower = content.question?.toLowerCase() || ''

      // Simple similarity scoring
      let matchCount = 0
      for (const word of words) {
        if (titleLower.includes(word) || questionLower.includes(word)) {
          matchCount++
        }
      }

      const similarity = words.length > 0 ? matchCount / words.length : 0

      if (similarity >= 0.5) {
        results.push({
          item,
          similarity,
          match_type: similarity >= 0.9 ? 'exact' : similarity >= 0.7 ? 'high' : 'medium',
        })
      }
    }

    results.sort((a, b) => b.similarity - a.similarity)
    const topResults = results.slice(0, 5)

    setDuplicates(topResults)
    setIsChecking(false)
    return topResults
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

// ==================== Categories Hook ====================

export function useCategories() {
  const [categories] = useState<KnowledgeCategory[]>(mockCategories)

  const getCategoryTree = useMemo(() => {
    const rootCategories = categories.filter((c) => !c.parent_id)
    const getChildren = (parentId: number): KnowledgeCategory[] => {
      return categories.filter((c) => c.parent_id === parentId)
    }

    return { rootCategories, getChildren }
  }, [categories])

  return {
    categories,
    ...getCategoryTree,
  }
}

// ==================== Variants Hook ====================

export function useVariants(knowledgeItemId: number) {
  const [variants, setVariants] = useState<KnowledgeVariant[]>(
    mockVariants.filter((v) => v.knowledge_item_id === knowledgeItemId)
  )
  const [isLoading, setIsLoading] = useState(false)

  const addVariant = useCallback(async (text: string): Promise<KnowledgeVariant> => {
    setIsLoading(true)
    await delay(300)

    const newVariant: KnowledgeVariant = {
      id: Math.max(...mockVariants.map((v) => v.id), 0) + 1,
      knowledge_item_id: knowledgeItemId,
      variant_text: text,
      source: 'manual',
      created_by: 'current-user',
      created_at: new Date().toISOString(),
    }

    setVariants((prev) => [...prev, newVariant])
    setIsLoading(false)
    return newVariant
  }, [knowledgeItemId])

  const deleteVariant = useCallback(async (variantId: number): Promise<void> => {
    setIsLoading(true)
    await delay(200)
    setVariants((prev) => prev.filter((v) => v.id !== variantId))
    setIsLoading(false)
  }, [])

  return {
    variants,
    isLoading,
    addVariant,
    deleteVariant,
  }
}

// ==================== Relationships Hook ====================

export function useRelationships(knowledgeItemId: number) {
  const [relationships, setRelationships] = useState<KnowledgeRelationship[]>(
    mockRelationships.filter(
      (r) => r.source_id === knowledgeItemId || r.target_id === knowledgeItemId
    )
  )
  const [isLoading, setIsLoading] = useState(false)

  // Populate with item details
  const populatedRelationships = useMemo(() => {
    return relationships.map((rel) => ({
      ...rel,
      source: mockKnowledgeItems.find((i) => i.id === rel.source_id),
      target: mockKnowledgeItems.find((i) => i.id === rel.target_id),
    }))
  }, [relationships])

  const addRelationship = useCallback(
    async (
      targetId: number,
      relationshipType: string,
      isBidirectional: boolean = false
    ): Promise<KnowledgeRelationship> => {
      setIsLoading(true)
      await delay(300)

      const newRel: KnowledgeRelationship = {
        id: Math.max(...mockRelationships.map((r) => r.id), 0) + 1,
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
      setIsLoading(false)
      return newRel
    },
    [knowledgeItemId]
  )

  const deleteRelationship = useCallback(async (relationshipId: number): Promise<void> => {
    setIsLoading(true)
    await delay(200)
    setRelationships((prev) => prev.filter((r) => r.id !== relationshipId))
    setIsLoading(false)
  }, [])

  return {
    relationships: populatedRelationships,
    isLoading,
    addRelationship,
    deleteRelationship,
  }
}

// ==================== Tags Hook ====================

export function useTags() {
  const [tags] = useState<string[]>(mockAllTags)

  const getPopularTags = useMemo(() => {
    // Count tag usage
    const tagCounts: Record<string, number> = {}
    for (const item of mockKnowledgeItems) {
      for (const tag of item.tags) {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1
      }
    }

    return Object.entries(tagCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([tag, count]) => ({ tag, count }))
  }, [])

  return {
    tags,
    popularTags: getPopularTags,
  }
}
