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
import { FAQDataTable, FAQFormDialog } from '@/components/faq'
import { useFAQs } from '@/hooks/useFAQ'
import type { FAQItem, FAQFormData } from '@/types/knowledge'

export function FAQPage() {
  const { items, createItem, updateItem, deleteItem } = useFAQs()
  const [formOpen, setFormOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<FAQItem | null>(null)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [itemToDelete, setItemToDelete] = useState<FAQItem | null>(null)

  const handleCreate = useCallback(() => {
    setEditingItem(null)
    setFormOpen(true)
  }, [])

  const handleEdit = useCallback((item: FAQItem) => {
    setEditingItem(item)
    setFormOpen(true)
  }, [])

  const handleDeleteClick = useCallback((item: FAQItem) => {
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
    async (data: FAQFormData) => {
      if (editingItem) {
        await updateItem(editingItem.id, data)
      } else {
        await createItem(data)
      }
    },
    [editingItem, createItem, updateItem]
  )

  const totalCount = items.length
  const publishedCount = items.filter((i) => i.status === 'published').length
  const draftCount = items.filter((i) => i.status === 'draft').length

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">FAQs</h1>
          <p className="text-muted-foreground">
            Manage frequently asked questions and their answers.
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Add FAQ
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total FAQs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCount}</div>
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
            <CardTitle className="text-sm font-medium">Drafts</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">{draftCount}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All FAQs</CardTitle>
          <CardDescription>
            Manage your FAQ entries. Click edit to modify or delete to remove.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <FAQDataTable
            data={items}
            onEdit={handleEdit}
            onDelete={handleDeleteClick}
          />
        </CardContent>
      </Card>

      <FAQFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        item={editingItem}
        onSubmit={handleFormSubmit}
      />

      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete FAQ</DialogTitle>
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
