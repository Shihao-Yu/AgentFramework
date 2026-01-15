import { useState, useCallback, useMemo } from 'react'
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
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { PermissionDataTable, PermissionFormDialog } from '@/components/permissions'
import { usePermissions } from '@/hooks/usePermissions'
import { useMetricsSummary } from '@/hooks/useMetricsSummary'
import type { PermissionItem, PermissionFormData } from '@/types/knowledge'

const PERMISSION_NODE_TYPES = ['permission_rule']

export function PermissionsPage() {
  const { 
    items, 
    allTags,
    pagination,
    filters,
    isLoading,
    existingPermissions, 
    existingRoles, 
    createItem, 
    updateItem, 
    deleteItem,
    updateFilters,
  } = usePermissions()
  
  const metricsSummaryOptions = useMemo(() => ({ nodeTypes: PERMISSION_NODE_TYPES }), [])
  const { summary: metricsSummary } = useMetricsSummary(metricsSummaryOptions)
  const [formOpen, setFormOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<PermissionItem | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [itemToDelete, setItemToDelete] = useState<PermissionItem | null>(null)
  const [viewItem, setViewItem] = useState<PermissionItem | null>(null)

  const handleCreate = useCallback(() => {
    setEditingItem(null)
    setFormOpen(true)
  }, [])

  const handleEdit = useCallback((item: PermissionItem) => {
    setEditingItem(item)
    setFormOpen(true)
  }, [])

  const handleView = useCallback((item: PermissionItem) => {
    setViewItem(item)
  }, [])

  const handleDeleteClick = useCallback((item: PermissionItem) => {
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
    async (data: PermissionFormData) => {
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

  const uniqueRolesCount = existingRoles.length

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Feature Permissions</h1>
          <p className="text-muted-foreground">
            Document what permissions are required to access each feature.
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add Feature
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Features</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metricsSummary.totalItems}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Published</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{metricsSummary.publishedItems}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Unique Roles</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{uniqueRolesCount}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Feature Permissions</CardTitle>
          <CardDescription>
            Define what permissions users need to access each feature.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PermissionDataTable
            data={items}
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

      <PermissionFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        item={editingItem}
        onSubmit={handleFormSubmit}
        existingPermissions={existingPermissions}
        existingRoles={existingRoles}
      />

      <Dialog open={!!viewItem} onOpenChange={() => setViewItem(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>{viewItem?.title}</DialogTitle>
            <DialogDescription>
              {viewItem?.content.description}
            </DialogDescription>
          </DialogHeader>
          {viewItem && (
            <ScrollArea className="max-h-[50vh]">
              <div className="space-y-4">
                <div>
                  <h4 className="font-medium mb-2 text-sm text-muted-foreground">Required Permissions</h4>
                  <div className="flex flex-wrap gap-2">
                    {viewItem.content.permissions.map((permission) => (
                      <Badge key={permission} variant="default" className="font-mono">
                        {permission}
                      </Badge>
                    ))}
                  </div>
                </div>

                <Separator />

                <div>
                  <h4 className="font-medium mb-2 text-sm text-muted-foreground">Roles with Access</h4>
                  <div className="flex flex-wrap gap-2">
                    {viewItem.content.roles.map((role) => (
                      <Badge key={role} variant="secondary">
                        {role}
                      </Badge>
                    ))}
                  </div>
                </div>

                {viewItem.content.context && (
                  <>
                    <Separator />
                    <div>
                      <h4 className="font-medium mb-2 text-sm text-muted-foreground">Additional Context</h4>
                      <div className="text-sm whitespace-pre-wrap bg-muted/50 p-3 rounded-md">
                        {viewItem.content.context}
                      </div>
                    </div>
                  </>
                )}

                {viewItem.tags.length > 0 && (
                  <>
                    <Separator />
                    <div>
                      <h4 className="font-medium mb-2 text-sm text-muted-foreground">Tags</h4>
                      <div className="flex flex-wrap gap-2">
                        {viewItem.tags.map((tag) => (
                          <Badge key={tag} variant="outline">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                <Separator />

                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span>Status: <Badge variant={viewItem.status === 'published' ? 'success' : 'secondary'} className="ml-1 capitalize">{viewItem.status}</Badge></span>
                  <span>Updated: {viewItem.updated_at ? new Date(viewItem.updated_at).toLocaleDateString() : 'Never'}</span>
                </div>
              </div>
            </ScrollArea>
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

      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Feature Permission</DialogTitle>
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
