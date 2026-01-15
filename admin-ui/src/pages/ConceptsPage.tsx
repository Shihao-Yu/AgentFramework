import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { NodeList } from '@/components/knowledge/NodeList'
import { KnowledgeNodeFormDialog } from '@/components/knowledge/KnowledgeNodeFormDialog'
import { useNodes } from '@/hooks/useNodes'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import {
  NodeType,
  type KnowledgeNode,
  type ConceptContent,
  type EntityContent,
  type Visibility,
  type NodeStatus,
} from '@/types/graph'

export function ConceptsPage() {
  const navigate = useNavigate()
  const { selectedTenantIds } = useTenantContext()
  const { 
    nodes, 
    allTags,
    pagination,
    filters,
    isLoading, 
    createNode,
    updateNode,
    deleteNode,
    updateFilters,
  } = useNodes({
    node_types: [NodeType.CONCEPT],
    tenant_ids: selectedTenantIds,
  })

  const [formOpen, setFormOpen] = useState(false)
  const [editingNode, setEditingNode] = useState<KnowledgeNode | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [nodeToDelete, setNodeToDelete] = useState<KnowledgeNode | null>(null)

  const handleView = useCallback((node: KnowledgeNode) => {
    navigate(`/graph?nodeId=${node.id}`)
  }, [navigate])

  const handleEdit = useCallback((node: KnowledgeNode) => {
    setEditingNode(node)
    setFormOpen(true)
  }, [])

  const handleDeleteClick = useCallback((node: KnowledgeNode) => {
    setNodeToDelete(node)
    setDeleteConfirmOpen(true)
  }, [])

  const handleDeleteConfirm = useCallback(async () => {
    if (nodeToDelete) {
      await deleteNode(nodeToDelete.id)
      setDeleteConfirmOpen(false)
      setNodeToDelete(null)
    }
  }, [nodeToDelete, deleteNode])

  const handleViewInGraph = useCallback((node: KnowledgeNode) => {
    navigate(`/graph?nodeId=${node.id}`)
  }, [navigate])

  const handleCreate = useCallback(() => {
    setEditingNode(null)
    setFormOpen(true)
  }, [])

  const handleFormSubmit = useCallback(async (data: {
    title: string
    tags: string[]
    status: NodeStatus
    visibility: Visibility
    content: ConceptContent | EntityContent
  }) => {
    const tenantId = selectedTenantIds[0] || 'default'
    
    if (editingNode) {
      await updateNode(editingNode.id, {
        title: data.title,
        tags: data.tags,
        status: data.status,
        visibility: data.visibility,
        content: data.content,
      })
    } else {
      await createNode({
        tenant_id: tenantId,
        node_type: NodeType.CONCEPT,
        title: data.title,
        tags: data.tags,
        status: data.status,
        visibility: data.visibility,
        content: data.content,
      })
    }
  }, [editingNode, selectedTenantIds, createNode, updateNode])

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
    <>
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
        onDelete={handleDeleteClick}
        onViewInGraph={handleViewInGraph}
        onCreate={handleCreate}
        onSearchChange={handleSearchChange}
        onTagsChange={handleTagsChange}
        onPageChange={handlePageChange}
        title="Concepts"
        description="Abstract hubs that connect related knowledge nodes"
      />

      <KnowledgeNodeFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        nodeType={NodeType.CONCEPT}
        node={editingNode}
        onSubmit={handleFormSubmit}
      />

      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Concept</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{nodeToDelete?.title}"? This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
