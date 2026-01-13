import { useEffect, useState, useCallback } from 'react'
import { useForm, type SubmitHandler } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2, X } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MonacoEditor, JSONEditor } from '@/components/editors'
import { exampleFormSchema, type ExampleFormData, type ExampleItem, type SchemaItem } from '@/types/knowledge'

interface ExampleFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  item?: ExampleItem | null
  schemas: SchemaItem[]
  defaultSchemaId?: number
  onSubmit: (data: ExampleFormData) => Promise<void>
}

export function ExampleFormDialog({
  open,
  onOpenChange,
  item,
  schemas,
  defaultSchemaId,
  onSubmit,
}: ExampleFormDialogProps) {
  const isEditing = !!item
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [jsonError, setJsonError] = useState<string>()

  const form = useForm<ExampleFormData>({
    mode: 'onChange',
    resolver: zodResolver(exampleFormSchema),
    defaultValues: {
      title: '',
      schema_id: defaultSchemaId || 0,
      description: '',
      content: '',
      format: 'text',
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
        schema_id: item.content.schema_id,
        description: item.content.description,
        content: item.content.content,
        format: item.content.format,
        tags: item.tags,
        status: item.status,
        visibility: item.visibility,
      })
    } else {
      form.reset({
        title: '',
        schema_id: defaultSchemaId || 0,
        description: '',
        content: '',
        format: 'text',
        tags: [],
        status: 'draft',
        visibility: 'internal',
      })
    }
    setJsonError(undefined)
  }, [item, form, defaultSchemaId])

  const handleSubmit: SubmitHandler<ExampleFormData> = async (data) => {
    // Validate JSON if format is json
    if (data.format === 'json') {
      try {
        JSON.parse(data.content)
      } catch {
        setJsonError('Invalid JSON format')
        return
      }
    }

    setIsSubmitting(true)
    try {
      await onSubmit(data)
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

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

  const tags = form.watch('tags')
  const format = form.watch('format')
  const content = form.watch('content')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Example' : 'Create New Example'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the example details below.'
              : 'Add a new example for this schema.'}
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4">
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">
                Title <span className="text-destructive">*</span>
              </Label>
              <Input
                id="title"
                placeholder="e.g., Find pending orders"
                {...form.register('title')}
              />
              {form.formState.errors.title && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.title.message}
                </p>
              )}
            </div>

            {/* Schema Selection */}
            <div className="space-y-2">
              <Label>
                Schema <span className="text-destructive">*</span>
              </Label>
              <Select
                value={form.watch('schema_id')?.toString() || ''}
                onValueChange={(value) => form.setValue('schema_id', parseInt(value))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a schema" />
                </SelectTrigger>
                <SelectContent>
                  {schemas.map((schema) => (
                    <SelectItem key={schema.id} value={schema.id.toString()}>
                      {schema.title} ({schema.content.name})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {form.formState.errors.schema_id && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.schema_id.message}
                </p>
              )}
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="description">
                Description <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="description"
                placeholder="Explain what this example demonstrates..."
                {...form.register('description')}
                className="min-h-[80px]"
              />
              {form.formState.errors.description && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.description.message}
                </p>
              )}
            </div>

            {/* Format Selection */}
            <div className="space-y-2">
              <Label>Content Format</Label>
              <Select
                value={format}
                onValueChange={(value: 'text' | 'json') => {
                  form.setValue('format', value)
                  setJsonError(undefined)
                }}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Text / Query</SelectItem>
                  <SelectItem value="json">JSON</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Content Editor */}
            <div className="space-y-2">
              <Label>
                Content <span className="text-destructive">*</span>
              </Label>
              {format === 'json' ? (
                <JSONEditor
                  value={content}
                  onChange={(val) => {
                    form.setValue('content', val)
                    setJsonError(undefined)
                  }}
                  height={200}
                  onValidationChange={(isValid, error) => {
                    setJsonError(isValid ? undefined : error)
                  }}
                />
              ) : (
                <MonacoEditor
                  value={content}
                  onChange={(val) => form.setValue('content', val)}
                  language="text"
                  height={200}
                />
              )}
              {(form.formState.errors.content || jsonError) && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.content?.message || jsonError}
                </p>
              )}
            </div>

            {/* Status and Visibility */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={form.watch('status')}
                  onValueChange={(value: ExampleFormData['status']) =>
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
                  onValueChange={(value: ExampleFormData['visibility']) =>
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
        </ScrollArea>

        <DialogFooter className="mt-4">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {isEditing && !form.formState.isDirty ? 'Close' : 'Cancel'}
          </Button>
          {(!isEditing || form.formState.isDirty) && (
            <Button
              onClick={form.handleSubmit(handleSubmit)}
              disabled={isSubmitting}
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? 'Save Changes' : 'Create Example'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
