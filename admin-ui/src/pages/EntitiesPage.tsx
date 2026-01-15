import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { NodeList } from '@/components/knowledge/NodeList'
import { useNodes } from '@/hooks/useNodes'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import { NodeType, type KnowledgeNode } from '@/types/graph'

export function EntitiesPage() {
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
    node_types: [NodeType.ENTITY],
    tenant_ids: selectedTenantIds,
  })

  const handleView = useCallback((node: KnowledgeNode) => {
    console.log('View entity:', node.id)
  }, [])

  const handleEdit = useCallback((node: KnowledgeNode) => {
    console.log('Edit entity:', node.id)
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
    console.log('Create new entity')
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
      nodeType={NodeType.ENTITY}
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
      title="Entities"
      description="Business domain models that map to technical schemas"
    />
  )
}
