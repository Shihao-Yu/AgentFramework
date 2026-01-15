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
import { MarkdownEditor } from '@/components/editors'
import { faqFormSchema, type FAQFormData, type FAQItem } from '@/types/knowledge'

interface FAQFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  item?: FAQItem | null
  onSubmit: (data: FAQFormData) => Promise<void>
}

export function FAQFormDialog({
  open,
  onOpenChange,
  item,
  onSubmit,
}: FAQFormDialogProps) {
  const isEditing = !!item
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagInput, setTagInput] = useState('')

  const form = useForm<FAQFormData>({
    mode: 'onChange',
    resolver: zodResolver(faqFormSchema),
    defaultValues: {
      title: '',
      question: '',
      answer: '',
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
        question: item.content.question,
        answer: item.content.answer,
        tags: item.tags,
        status: item.status,
        visibility: item.visibility,
      })
    } else {
      form.reset({
        title: '',
        question: '',
        answer: '',
        tags: [],
        status: 'draft',
        visibility: 'internal',
      })
    }
  }, [item, form])

  const handleSubmit: SubmitHandler<FAQFormData> = async (data) => {
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
      form.setValue('tags', [...form.getValues('tags'), tag], { shouldDirty: true })
    }
    setTagInput('')
  }, [tagInput, form])

  const removeTag = useCallback(
    (tagToRemove: string) => {
      form.setValue(
        'tags',
        form.getValues('tags').filter((t) => t !== tagToRemove),
        { shouldDirty: true }
      )
    },
    [form]
  )

  const tags = form.watch('tags')
  const answer = form.watch('answer')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col gap-0">
        <DialogHeader className="pb-4 border-b">
          <DialogTitle>{isEditing ? 'Edit FAQ' : 'Create New FAQ'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the FAQ details below.'
              : 'Fill in the details to create a new FAQ entry. The answer supports Markdown.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 pr-2">
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">
                Title <span className="text-destructive">*</span>
              </Label>
              <Input
                id="title"
                placeholder="Short descriptive title"
                {...form.register('title')}
              />
              {form.formState.errors.title && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.title.message}
                </p>
              )}
            </div>

            {/* Question */}
            <div className="space-y-2">
              <Label htmlFor="question">
                Question <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="question"
                placeholder="e.g., How do I create a purchase order?"
                {...form.register('question')}
                className="min-h-[80px]"
              />
              {form.formState.errors.question && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.question.message}
                </p>
              )}
            </div>

            {/* Answer (Markdown) */}
            <div className="space-y-2">
              <Label>
                Answer <span className="text-destructive">*</span>
              </Label>
              <MarkdownEditor
                value={answer}
                onChange={(val) => form.setValue('answer', val, { shouldDirty: true })}
                placeholder="Provide a clear, detailed answer... (Markdown supported)"
                height={250}
              />
              {form.formState.errors.answer && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.answer.message}
                </p>
              )}
            </div>

            {/* Status and Visibility */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={form.watch('status')}
                  onValueChange={(value: FAQFormData['status']) =>
                    form.setValue('status', value, { shouldDirty: true })
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
                  onValueChange={(value: FAQFormData['visibility']) =>
                    form.setValue('visibility', value, { shouldDirty: true })
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
            Cancel
          </Button>
          <Button
            onClick={form.handleSubmit(handleSubmit)}
            disabled={isSubmitting || (isEditing && !form.formState.isDirty)}
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEditing ? 'Save Changes' : 'Create FAQ'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
