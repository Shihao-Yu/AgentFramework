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
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MarkdownEditor } from '@/components/editors/MarkdownEditor'
import { permissionFormSchema, type PermissionFormData, type PermissionItem } from '@/types/knowledge'

interface PermissionFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  item?: PermissionItem | null
  onSubmit: (data: PermissionFormData) => Promise<void>
  existingPermissions?: string[]
  existingRoles?: string[]
}

export function PermissionFormDialog({
  open,
  onOpenChange,
  item,
  onSubmit,
  existingPermissions = [],
  existingRoles = [],
}: PermissionFormDialogProps) {
  const isEditing = !!item
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [permissionInput, setPermissionInput] = useState('')
  const [roleInput, setRoleInput] = useState('')

  const form = useForm<PermissionFormData>({
    mode: 'onChange',
    resolver: zodResolver(permissionFormSchema),
    defaultValues: {
      title: '',
      description: '',
      permissions: [],
      roles: [],
      context: '',
      tags: [],
      status: 'draft',
      visibility: 'internal',
    },
  })

  useEffect(() => {
    if (item) {
      form.reset({
        title: item.title,
        description: item.content.description,
        permissions: item.content.permissions,
        roles: item.content.roles,
        context: item.content.context || '',
        tags: item.tags,
        status: item.status,
        visibility: item.visibility,
      })
    } else {
      form.reset({
        title: '',
        description: '',
        permissions: [],
        roles: [],
        context: '',
        tags: [],
        status: 'draft',
        visibility: 'internal',
      })
    }
  }, [item, form])

  const handleSubmit: SubmitHandler<PermissionFormData> = async (data) => {
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

  const addPermission = useCallback(() => {
    const permission = permissionInput.trim().toLowerCase()
    if (permission && !form.getValues('permissions').includes(permission)) {
      form.setValue('permissions', [...form.getValues('permissions'), permission])
    }
    setPermissionInput('')
  }, [permissionInput, form])

  const removePermission = useCallback(
    (permissionToRemove: string) => {
      form.setValue(
        'permissions',
        form.getValues('permissions').filter((p) => p !== permissionToRemove)
      )
    },
    [form]
  )

  const addRole = useCallback(() => {
    const role = roleInput.trim()
    if (role && !form.getValues('roles').includes(role)) {
      form.setValue('roles', [...form.getValues('roles'), role])
    }
    setRoleInput('')
  }, [roleInput, form])

  const removeRole = useCallback(
    (roleToRemove: string) => {
      form.setValue(
        'roles',
        form.getValues('roles').filter((r) => r !== roleToRemove)
      )
    },
    [form]
  )

  const tags = form.watch('tags')
  const permissions = form.watch('permissions')
  const roles = form.watch('roles')
  const contextValue = form.watch('context') || ''

  const suggestedPermissions = existingPermissions.filter((p) => !permissions.includes(p)).slice(0, 5)
  const suggestedRoles = existingRoles.filter((r) => !roles.includes(r)).slice(0, 5)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] flex flex-col gap-0">
        <DialogHeader className="pb-4 border-b">
          <DialogTitle>{isEditing ? 'Edit Feature Permission' : 'Add Feature Permission'}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Update the feature permission details below.'
              : 'Document what permissions are required to access a feature.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 pr-2">
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="title">
                Feature Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="title"
                placeholder="e.g., Export Reports"
                {...form.register('title')}
              />
              {form.formState.errors.title && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.title.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">
                Description <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="description"
                placeholder="What does this feature do? e.g., Allows users to export data to CSV/Excel formats"
                rows={3}
                {...form.register('description')}
              />
              {form.formState.errors.description && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.description.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>
                Required Permissions <span className="text-destructive">*</span>
              </Label>
              <div className="flex gap-2">
                <Input
                  placeholder="e.g., reports.export"
                  value={permissionInput}
                  onChange={(e) => setPermissionInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addPermission()
                    }
                  }}
                />
                <Button type="button" variant="secondary" onClick={addPermission}>
                  Add
                </Button>
              </div>
              {form.formState.errors.permissions && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.permissions.message}
                </p>
              )}
              {suggestedPermissions.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  <span className="text-xs text-muted-foreground mr-2">Suggestions:</span>
                  {suggestedPermissions.map((permission) => (
                    <Badge
                      key={permission}
                      variant="outline"
                      className="cursor-pointer hover:bg-secondary"
                      onClick={() => {
                        form.setValue('permissions', [...form.getValues('permissions'), permission])
                      }}
                    >
                      + {permission}
                    </Badge>
                  ))}
                </div>
              )}
              {permissions.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {permissions.map((permission) => (
                    <Badge key={permission} variant="default" className="gap-1 font-mono text-xs">
                      {permission}
                      <button
                        type="button"
                        onClick={() => removePermission(permission)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>
                Roles with Access <span className="text-destructive">*</span>
              </Label>
              <div className="flex gap-2">
                <Input
                  placeholder="e.g., Admin, Finance Manager"
                  value={roleInput}
                  onChange={(e) => setRoleInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      addRole()
                    }
                  }}
                />
                <Button type="button" variant="secondary" onClick={addRole}>
                  Add
                </Button>
              </div>
              {form.formState.errors.roles && (
                <p className="text-sm text-destructive">
                  {form.formState.errors.roles.message}
                </p>
              )}
              {suggestedRoles.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  <span className="text-xs text-muted-foreground mr-2">Suggestions:</span>
                  {suggestedRoles.map((role) => (
                    <Badge
                      key={role}
                      variant="outline"
                      className="cursor-pointer hover:bg-secondary"
                      onClick={() => {
                        form.setValue('roles', [...form.getValues('roles'), role])
                      }}
                    >
                      + {role}
                    </Badge>
                  ))}
                </div>
              )}
              {roles.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {roles.map((role) => (
                    <Badge key={role} variant="secondary" className="gap-1">
                      {role}
                      <button
                        type="button"
                        onClick={() => removeRole(role)}
                        className="ml-1 hover:text-destructive"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>Additional Context</Label>
              <p className="text-xs text-muted-foreground">
                Add any edge cases, exceptions, or additional notes (Markdown supported)
              </p>
              <MarkdownEditor
                value={contextValue}
                onChange={(value) => form.setValue('context', value)}
                height={150}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Status</Label>
                <Select
                  value={form.watch('status')}
                  onValueChange={(value: PermissionFormData['status']) =>
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
                  onValueChange={(value: PermissionFormData['visibility']) =>
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
                    <Badge key={tag} variant="outline" className="gap-1">
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
              {isEditing ? 'Save Changes' : 'Add Feature'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
