import { useState, useCallback } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { PlaybookDataTable, PlaybookFormDialog } from '@/components/playbooks'
import { MarkdownPreview } from '@/components/editors'
import { usePlaybooks } from '@/hooks/usePlaybooks'
import type { PlaybookItem, PlaybookFormData } from '@/types/knowledge'

export function PlaybooksPage() {
  const { 
    items, 
    domains, 
    allTags,
    pagination,
    filters,
    isLoading,
    createItem, 
    updateItem, 
    deleteItem, 
    updateFilters,
    addCustomDomain 
  } = usePlaybooks()
  const [formOpen, setFormOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<PlaybookItem | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [itemToDelete, setItemToDelete] = useState<PlaybookItem | null>(null)
  const [viewItem, setViewItem] = useState<PlaybookItem | null>(null)

  const handleCreate = useCallback(() => {
    setEditingItem(null)
    setFormOpen(true)
  }, [])

  const handleEdit = useCallback((item: PlaybookItem) => {
    setEditingItem(item)
    setFormOpen(true)
  }, [])

  const handleView = useCallback((item: PlaybookItem) => {
    setViewItem(item)
  }, [])

  const handleDeleteClick = useCallback((item: PlaybookItem) => {
    setItemToDelete(item)
    setDeleteConfirmOpen(true)
  }, [])

  const handleDeleteConfirm = useCallback(async () => {
    if (itemToDelete) {
      await deleteItem(itemToDelete.id)
      setDeleteConfirmOpen(false)
      setItemToDelete(null)
    }
  }, [itemToDelete, deleteItem])

  const handleFormSubmit = useCallback(
    async (data: PlaybookFormData) => {
      if (editingItem) {
        await updateItem(editingItem.id, data)
      } else {
        await createItem(data)
      }
    },
    [editingItem, createItem, updateItem]
  )

  const handleSearchChange = useCallback((search: string) => {
    updateFilters({ search })
  }, [updateFilters])

  const handleTagsChange = useCallback((tags: string[]) => {
    updateFilters({ tags })
  }, [updateFilters])

  const handlePageChange = useCallback((page: number) => {
    updateFilters({ page })
  }, [updateFilters])

  const getDomainName = (domainId: string) => {
    const domain = domains.find((d) => d.id === domainId)
    return domain?.name || domainId
  }

  // Stats
  const publishedCount = items.filter((i) => i.status === 'published').length
  const uniqueDomains = new Set(items.map((i) => i.content.domain)).size

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Playbooks</h1>
          <p className="text-muted-foreground">
            Create and manage domain-specific guides and documentation.
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add Playbook
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Playbooks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pagination.total}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Published</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{publishedCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Domains Covered</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{uniqueDomains}</div>
          </CardContent>
        </Card>
      </div>

      {/* Data Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Playbooks</CardTitle>
          <CardDescription>
            Domain-specific guides, procedures, and documentation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PlaybookDataTable
            data={items}
            domains={domains}
            allTags={allTags}
            pagination={pagination}
            selectedTags={filters.tags || []}
            searchValue={filters.search || ''}
            isLoading={isLoading}
            onView={handleView}
            onEdit={handleEdit}
            onDelete={handleDeleteClick}
            onSearchChange={handleSearchChange}
            onTagsChange={handleTagsChange}
            onPageChange={handlePageChange}
          />
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <PlaybookFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        item={editingItem}
        domains={domains}
        onSubmit={handleFormSubmit}
        onAddDomain={addCustomDomain}
      />

      {/* View Dialog */}
      <Dialog open={!!viewItem} onOpenChange={() => setViewItem(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>{viewItem?.title}</DialogTitle>
            <DialogDescription className="flex items-center gap-2">
              <Badge variant="outline">
                {viewItem && getDomainName(viewItem.content.domain)}
              </Badge>
              <span>
                Last updated:{' '}
                {viewItem?.updated_at
                  ? new Date(viewItem.updated_at).toLocaleDateString()
                  : 'Never'}
              </span>
            </DialogDescription>
          </DialogHeader>
          {viewItem && (
            <div className="space-y-4">
              <div className="border rounded-md p-4 bg-muted/30">
                <MarkdownPreview content={viewItem.content.content} />
              </div>
              {viewItem.tags.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {viewItem.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewItem(null)}>
              Close
            </Button>
            <Button
              onClick={() => {
                if (viewItem) {
                  handleEdit(viewItem)
                  setViewItem(null)
                }
              }}
            >
              Edit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Playbook</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{itemToDelete?.title}"? This action
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
    </div>
  )
}
