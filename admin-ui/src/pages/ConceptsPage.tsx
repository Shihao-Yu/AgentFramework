import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { NodeList } from '@/components/knowledge/NodeList'
import { useNodes } from '@/hooks/useNodes'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import { NodeType, type KnowledgeNode } from '@/types/graph'

export function ConceptsPage() {
  const navigate = useNavigate()
  const { selectedTenantIds } = useTenantContext()
  const { 
    nodes, 
    allTags,
    pagination,
    filters,
    isLoading, 
    deleteNode,
    updateFilters,
  } = useNodes({
    node_types: [NodeType.CONCEPT],
    tenant_ids: selectedTenantIds,
  })

  const handleView = useCallback((node: KnowledgeNode) => {
    console.log('View concept:', node.id)
  }, [])

  const handleEdit = useCallback((node: KnowledgeNode) => {
    console.log('Edit concept:', node.id)
  }, [])

  const handleDelete = useCallback(async (node: KnowledgeNode) => {
    if (confirm(`Are you sure you want to delete "${node.title}"?`)) {
      await deleteNode(node.id)
    }
  }, [deleteNode])

  const handleViewInGraph = useCallback((node: KnowledgeNode) => {
    navigate(`/graph?nodeId=${node.id}`)
  }, [navigate])

  const handleCreate = useCallback(() => {
    console.log('Create new concept')
  }, [])

  const handleSearchChange = useCallback((search: string) => {
    updateFilters({ search })
  }, [updateFilters])

  const handleTagsChange = useCallback((tags: string[]) => {
    updateFilters({ tags })
  }, [updateFilters])

  const handlePageChange = useCallback((page: number) => {
    updateFilters({ page })
  }, [updateFilters])

  return (
    <NodeList
      nodes={nodes}
      nodeType={NodeType.CONCEPT}
      allTags={allTags}
      pagination={pagination}
      selectedTags={filters.tags || []}
      searchValue={filters.search || ''}
      isLoading={isLoading}
      onView={handleView}
      onEdit={handleEdit}
      onDelete={handleDelete}
      onViewInGraph={handleViewInGraph}
      onCreate={handleCreate}
      onSearchChange={handleSearchChange}
      onTagsChange={handleTagsChange}
      onPageChange={handlePageChange}
      title="Concepts"
      description="Abstract hubs that connect related knowledge nodes"
    />
  )
}
