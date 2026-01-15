import { useEffect, useState, useCallback } from 'react'
import { useForm, type SubmitHandler } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2, X, Plus } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MarkdownEditor } from '@/components/editors'
import { playbookFormSchema, type PlaybookFormData, type PlaybookItem, type Domain } from '@/types/knowledge'

interface PlaybookFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  item?: PlaybookItem | null
  domains: Domain[]
  onSubmit: (data: PlaybookFormData) => Promise<void>
  onAddDomain?: (name: string) => void
}

export function PlaybookFormDialog({
  open,
  onOpenChange,
  item,
  domains,
  onSubmit,
  onAddDomain,
}: PlaybookFormDialogProps) {
  const isEditing = !!item
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [newDomainInput, setNewDomainInput] = useState('')
  const [showNewDomainInput, setShowNewDomainInput] = useState(false)

  const form = useForm<PlaybookFormData>({
    mode: 'onChange',
    resolver: zodResolver(playbookFormSchema),
    defaultValues: {
      title: '',
      domain: '',
      content: '',
      tags: [],
      status: 'draft',
      visibility: 'internal',
    },
  })

  // Reset form when item changes
  useEffect(() => {
    if (item) {
      form.reset({
        title: item.title,
        domain: item.content.domain,
        content: item.content.content,
        tags: item.tags,
        status: item.status,
        visibility: item.visibility,
      })
    } else {
      form.reset({
        title: '',
        domain: '',
        content: '',
        tags: [],
        status: 'draft',
        visibility: 'internal',
      })
    }
    setShowNewDomainInput(false)
    setNewDomainInput('')
  }, [item, form])

  const handleSubmit: SubmitHandler<PlaybookFormData> = async (data) => {
    setIsSubmitting(true)
    try {
      await onSubmit(data)
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  // Tag management
  const addTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase()
    if (tag && !form.getValues('tags').includes(tag)) {
      form.setValue('tags', [...form.getValues('tags'), tag])
    }
    setTagInput('')
  }, [tagInput, form])

  const removeTag = useCallback(
    (tagToRemove: string) => {
      form.setValue(
        'tags',
        form.getValues('tags').filter((t) => t !== tagToRemove)
      )
    },
    [form]
  )

  // Add new domain
  const handleAddNewDomain = useCallback(() => {
    if (newDomainInput.trim() && onAddDomain) {
      onAddDomain(newDomainInput.trim())
      form.setValue('domain', newDomainInput.toLowerCase().replace(/\s+/g, '-'))
      setNewDomainInput('')
      setShowNewDomainInput(false)
    }
  }, [newDomainInput, onAddDomain, form])

  const tags = form.watch('tags')
  const content = form.watch('content')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col gap-0">
        <DialogHeader className="pb-4 border-b">
          <DialogTitle>{isEditing ? 'Edit Playbook' : 'Create New Playbook'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the playbook details below.'
              : 'Create a new playbook with Markdown content.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 pr-2">
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="title">
                Title <span className="text-destructive">*</span>
              </Label>
              <Input
                id="title"
                placeholder="e.g., Purchase Order Creation Guide"
                {...form.register('title')}
              />
              {form.formState.errors.title && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.title.message}
                </p>
              )}
            </div>

            {/* Domain */}
            <div className="space-y-2">
              <Label>
                Domain <span className="text-destructive">*</span>
              </Label>
              {!showNewDomainInput ? (
                <div className="flex gap-2">
                  <Select
                    value={form.watch('domain')}
                    onValueChange={(value) => form.setValue('domain', value)}
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder="Select a domain" />
                    </SelectTrigger>
                    <SelectContent>
                      {domains.map((domain) => (
                        <SelectItem key={domain.id} value={domain.id}>
                          <div className="flex items-center gap-2">
                            {domain.name}
                            {domain.isCustom && (
                              <Badge variant="outline" className="text-xs">
                                custom
                              </Badge>
                            )}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {onAddDomain && (
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowNewDomainInput(true)}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ) : (
                <div className="flex gap-2">
                  <Input
                    placeholder="New domain name..."
                    value={newDomainInput}
                    onChange={(e) => setNewDomainInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleAddNewDomain()
                      }
                    }}
                  />
                  <Button type="button" variant="secondary" onClick={handleAddNewDomain}>
                    Add
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setShowNewDomainInput(false)
                      setNewDomainInput('')
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              )}
              {form.formState.errors.domain && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.domain.message}
                </p>
              )}
            </div>

            {/* Content (Markdown) */}
            <div className="space-y-2">
              <Label>
                Content <span className="text-destructive">*</span>
              </Label>
              <MarkdownEditor
                value={content}
                onChange={(val) => form.setValue('content', val)}
                placeholder="Write your playbook content using Markdown..."
                height={350}
              />
              {form.formState.errors.content && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.content.message}
                </p>
              )}
            </div>

            {/* Status and Visibility */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={form.watch('status')}
                  onValueChange={(value: PlaybookFormData['status']) =>
                    form.setValue('status', value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="published">Published</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Visibility</Label>
                <Select
                  value={form.watch('visibility')}
                  onValueChange={(value: PlaybookFormData['visibility']) =>
                    form.setValue('visibility', value)
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">Public</SelectItem>
                    <SelectItem value="internal">Internal</SelectItem>
                    <SelectItem value="restricted">Restricted</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Tags */}
            <div className="space-y-2">
              <Label>Tags</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Add a tag..."
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addTag()
                    }
                  }}
                />
                <Button type="button" variant="secondary" onClick={addTag}>
                  Add
                </Button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="gap-1">
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </form>
        </div>

        <DialogFooter className="pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {isEditing && !form.formState.isDirty ? 'Close' : 'Cancel'}
          </Button>
          {(!isEditing || form.formState.isDirty) && (
            <Button
              onClick={form.handleSubmit(handleSubmit)}
              disabled={isSubmitting}
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Save Changes' : 'Create Playbook'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
