import { useEffect, useState, useCallback } from 'react'
import { useForm, type SubmitHandler, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Loader2, X, Plus, Trash2 } from 'lucide-react'
import { z } from 'zod'
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
import {
  NodeType,
  NodeTypeLabels,
  type KnowledgeNode,
  type ConceptContent,
  type EntityContent,
  type Visibility,
  type NodeStatus,
} from '@/types/graph'

const conceptFormSchema = z.object({
  title: z.string().min(3, 'Title must be at least 3 characters'),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  aliases: z.array(z.string()),
  scope: z.string().optional(),
  key_questions: z.array(z.string()),
})

const entityFormSchema = z.object({
  title: z.string().min(3, 'Title must be at least 3 characters'),
  tags: z.array(z.string()),
  status: z.enum(['draft', 'published', 'archived']),
  visibility: z.enum(['public', 'internal', 'restricted']),
  entity_name: z.string().min(1, 'Entity name is required'),
  entity_path: z.string().min(1, 'Entity path is required'),
  parent_entity: z.string().optional(),
  child_entities: z.array(z.string()),
  description: z.string().min(10, 'Description must be at least 10 characters'),
  business_purpose: z.string().optional(),
  key_attributes: z.array(z.object({
    name: z.string().min(1, 'Name is required'),
    type: z.string().min(1, 'Type is required'),
    description: z.string().optional(),
  })),
  common_queries: z.array(z.string()),
})

type ConceptFormData = z.infer<typeof conceptFormSchema>
type EntityFormData = z.infer<typeof entityFormSchema>

interface KnowledgeNodeFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  nodeType: typeof NodeType.CONCEPT | typeof NodeType.ENTITY
  node?: KnowledgeNode | null
  onSubmit: (data: {
    title: string
    tags: string[]
    status: NodeStatus
    visibility: Visibility
    content: ConceptContent | EntityContent
  }) => Promise<void>
}

export function KnowledgeNodeFormDialog({
  open,
  onOpenChange,
  nodeType,
  node,
  onSubmit,
}: KnowledgeNodeFormDialogProps) {
  const isEditing = !!node
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [aliasInput, setAliasInput] = useState('')
  const [questionInput, setQuestionInput] = useState('')
  const [childEntityInput, setChildEntityInput] = useState('')
  const [queryInput, setQueryInput] = useState('')

  const isConcept = nodeType === NodeType.CONCEPT

  const conceptForm = useForm<ConceptFormData>({
    mode: 'onChange',
    resolver: zodResolver(conceptFormSchema),
    defaultValues: {
      title: '',
      tags: [],
      status: 'draft',
      visibility: 'internal',
      description: '',
      aliases: [],
      scope: '',
      key_questions: [],
    },
  })

  const entityForm = useForm<EntityFormData>({
    mode: 'onChange',
    resolver: zodResolver(entityFormSchema),
    defaultValues: {
      title: '',
      tags: [],
      status: 'draft',
      visibility: 'internal',
      entity_name: '',
      entity_path: '',
      parent_entity: '',
      child_entities: [],
      description: '',
      business_purpose: '',
      key_attributes: [],
      common_queries: [],
    },
  })

  const { fields: attributeFields, append: appendAttribute, remove: removeAttribute } = useFieldArray({
    control: entityForm.control,
    name: 'key_attributes',
  })

  useEffect(() => {
    if (isConcept) {
      if (node && node.node_type === NodeType.CONCEPT) {
        const content = node.content as ConceptContent
        conceptForm.reset({
          title: node.title,
          tags: node.tags,
          status: node.status,
          visibility: node.visibility,
          description: content.description,
          aliases: content.aliases || [],
          scope: content.scope || '',
          key_questions: content.key_questions || [],
        })
      } else {
        conceptForm.reset({
          title: '',
          tags: [],
          status: 'draft',
          visibility: 'internal',
          description: '',
          aliases: [],
          scope: '',
          key_questions: [],
        })
      }
    } else {
      if (node && node.node_type === NodeType.ENTITY) {
        const content = node.content as EntityContent
        entityForm.reset({
          title: node.title,
          tags: node.tags,
          status: node.status,
          visibility: node.visibility,
          entity_name: content.entity_name,
          entity_path: content.entity_path,
          parent_entity: content.parent_entity || '',
          child_entities: content.child_entities || [],
          description: content.description,
          business_purpose: content.business_purpose || '',
          key_attributes: content.key_attributes || [],
          common_queries: content.common_queries || [],
        })
      } else {
        entityForm.reset({
          title: '',
          tags: [],
          status: 'draft',
          visibility: 'internal',
          entity_name: '',
          entity_path: '',
          parent_entity: '',
          child_entities: [],
          description: '',
          business_purpose: '',
          key_attributes: [],
          common_queries: [],
        })
      }
    }
  }, [node, isConcept, conceptForm, entityForm])

  const handleConceptSubmit: SubmitHandler<ConceptFormData> = async (data) => {
    setIsSubmitting(true)
    try {
      const content: ConceptContent = {
        description: data.description,
        aliases: data.aliases.length > 0 ? data.aliases : undefined,
        scope: data.scope || undefined,
        key_questions: data.key_questions.length > 0 ? data.key_questions : undefined,
      }
      await onSubmit({
        title: data.title,
        tags: data.tags,
        status: data.status,
        visibility: data.visibility,
        content,
      })
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleEntitySubmit: SubmitHandler<EntityFormData> = async (data) => {
    setIsSubmitting(true)
    try {
      const content: EntityContent = {
        entity_name: data.entity_name,
        entity_path: data.entity_path,
        parent_entity: data.parent_entity || undefined,
        child_entities: data.child_entities.length > 0 ? data.child_entities : undefined,
        description: data.description,
        business_purpose: data.business_purpose || undefined,
        key_attributes: data.key_attributes.length > 0 ? data.key_attributes : undefined,
        common_queries: data.common_queries.length > 0 ? data.common_queries : undefined,
      }
      await onSubmit({
        title: data.title,
        tags: data.tags,
        status: data.status,
        visibility: data.visibility,
        content,
      })
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  const addConceptTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase()
    if (tag && !conceptForm.getValues('tags').includes(tag)) {
      conceptForm.setValue('tags', [...conceptForm.getValues('tags'), tag], { shouldDirty: true })
    }
    setTagInput('')
  }, [tagInput, conceptForm])

  const removeConceptTag = useCallback((tagToRemove: string) => {
    conceptForm.setValue(
      'tags',
      conceptForm.getValues('tags').filter((t) => t !== tagToRemove),
      { shouldDirty: true }
    )
  }, [conceptForm])

  const addEntityTag = useCallback(() => {
    const tag = tagInput.trim().toLowerCase()
    if (tag && !entityForm.getValues('tags').includes(tag)) {
      entityForm.setValue('tags', [...entityForm.getValues('tags'), tag], { shouldDirty: true })
    }
    setTagInput('')
  }, [tagInput, entityForm])

  const removeEntityTag = useCallback((tagToRemove: string) => {
    entityForm.setValue(
      'tags',
      entityForm.getValues('tags').filter((t) => t !== tagToRemove),
      { shouldDirty: true }
    )
  }, [entityForm])

  const addAlias = useCallback(() => {
    const alias = aliasInput.trim()
    if (alias && !conceptForm.getValues('aliases').includes(alias)) {
      conceptForm.setValue('aliases', [...conceptForm.getValues('aliases'), alias], { shouldDirty: true })
    }
    setAliasInput('')
  }, [aliasInput, conceptForm])

  const removeAlias = useCallback((aliasToRemove: string) => {
    conceptForm.setValue(
      'aliases',
      conceptForm.getValues('aliases').filter((a) => a !== aliasToRemove),
      { shouldDirty: true }
    )
  }, [conceptForm])

  const addKeyQuestion = useCallback(() => {
    const question = questionInput.trim()
    if (question && !conceptForm.getValues('key_questions').includes(question)) {
      conceptForm.setValue('key_questions', [...conceptForm.getValues('key_questions'), question], { shouldDirty: true })
    }
    setQuestionInput('')
  }, [questionInput, conceptForm])

  const removeKeyQuestion = useCallback((questionToRemove: string) => {
    conceptForm.setValue(
      'key_questions',
      conceptForm.getValues('key_questions').filter((q) => q !== questionToRemove),
      { shouldDirty: true }
    )
  }, [conceptForm])

  const addChildEntity = useCallback(() => {
    const child = childEntityInput.trim()
    if (child && !entityForm.getValues('child_entities').includes(child)) {
      entityForm.setValue('child_entities', [...entityForm.getValues('child_entities'), child], { shouldDirty: true })
    }
    setChildEntityInput('')
  }, [childEntityInput, entityForm])

  const removeChildEntity = useCallback((childToRemove: string) => {
    entityForm.setValue(
      'child_entities',
      entityForm.getValues('child_entities').filter((c) => c !== childToRemove),
      { shouldDirty: true }
    )
  }, [entityForm])

  const addCommonQuery = useCallback(() => {
    const query = queryInput.trim()
    if (query && !entityForm.getValues('common_queries').includes(query)) {
      entityForm.setValue('common_queries', [...entityForm.getValues('common_queries'), query], { shouldDirty: true })
    }
    setQueryInput('')
  }, [queryInput, entityForm])

  const removeCommonQuery = useCallback((queryToRemove: string) => {
    entityForm.setValue(
      'common_queries',
      entityForm.getValues('common_queries').filter((q) => q !== queryToRemove),
      { shouldDirty: true }
    )
  }, [entityForm])

  const conceptTags = conceptForm.watch('tags')
  const entityTags = entityForm.watch('tags')
  const aliases = conceptForm.watch('aliases')
  const keyQuestions = conceptForm.watch('key_questions')
  const childEntities = entityForm.watch('child_entities')
  const commonQueries = entityForm.watch('common_queries')

  const nodeTypeLabel = NodeTypeLabels[nodeType]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col gap-0">
        <DialogHeader className="pb-4 border-b">
          <DialogTitle>{isEditing ? `Edit ${nodeTypeLabel}` : `Create New ${nodeTypeLabel}`}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? `Update the ${nodeTypeLabel.toLowerCase()} details below.`
              : `Fill in the details to create a new ${nodeTypeLabel.toLowerCase()}.`}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 pr-2">
          {isConcept ? (
            <form onSubmit={conceptForm.handleSubmit(handleConceptSubmit)} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="title">
                  Title <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="title"
                  placeholder="Concept name"
                  {...conceptForm.register('title')}
                />
                {conceptForm.formState.errors.title && (
                  <p className="text-sm text-destructive">
                    {conceptForm.formState.errors.title.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">
                  Description <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="description"
                  placeholder="Describe this concept..."
                  {...conceptForm.register('description')}
                  className="min-h-[100px]"
                />
                {conceptForm.formState.errors.description && (
                  <p className="text-sm text-destructive">
                    {conceptForm.formState.errors.description.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="scope">Scope</Label>
                <Input
                  id="scope"
                  placeholder="e.g., Purchasing Department, Finance"
                  {...conceptForm.register('scope')}
                />
              </div>

              <div className="space-y-2">
                <Label>Aliases</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Add an alias..."
                    value={aliasInput}
                    onChange={(e) => setAliasInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addAlias()
                      }
                    }}
                  />
                  <Button type="button" variant="secondary" onClick={addAlias}>
                    Add
                  </Button>
                </div>
                {aliases.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {aliases.map((alias) => (
                      <Badge key={alias} variant="secondary" className="gap-1">
                        {alias}
                        <button
                          type="button"
                          onClick={() => removeAlias(alias)}
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
                <Label>Key Questions</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Add a key question..."
                    value={questionInput}
                    onChange={(e) => setQuestionInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addKeyQuestion()
                      }
                    }}
                  />
                  <Button type="button" variant="secondary" onClick={addKeyQuestion}>
                    Add
                  </Button>
                </div>
                {keyQuestions.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {keyQuestions.map((question, index) => (
                      <li key={index} className="flex items-center gap-2 text-sm">
                        <span className="flex-1">{question}</span>
                        <button
                          type="button"
                          onClick={() => removeKeyQuestion(question)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select
                    value={conceptForm.watch('status')}
                    onValueChange={(value: ConceptFormData['status']) =>
                      conceptForm.setValue('status', value, { shouldDirty: true })
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
                    value={conceptForm.watch('visibility')}
                    onValueChange={(value: ConceptFormData['visibility']) =>
                      conceptForm.setValue('visibility', value, { shouldDirty: true })
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
                        addConceptTag()
                      }
                    }}
                  />
                  <Button type="button" variant="secondary" onClick={addConceptTag}>
                    Add
                  </Button>
                </div>
                {conceptTags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {conceptTags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="gap-1">
                        {tag}
                        <button
                          type="button"
                          onClick={() => removeConceptTag(tag)}
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
          ) : (
            <form onSubmit={entityForm.handleSubmit(handleEntitySubmit)} className="space-y-6">
              <div className="space-y-2">
                <Label htmlFor="title">
                  Title <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="title"
                  placeholder="Entity display name"
                  {...entityForm.register('title')}
                />
                {entityForm.formState.errors.title && (
                  <p className="text-sm text-destructive">
                    {entityForm.formState.errors.title.message}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="entity_name">
                    Entity Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="entity_name"
                    placeholder="e.g., PurchaseOrder"
                    {...entityForm.register('entity_name')}
                    className="font-mono"
                  />
                  {entityForm.formState.errors.entity_name && (
                    <p className="text-sm text-destructive">
                      {entityForm.formState.errors.entity_name.message}
                    </p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="entity_path">
                    Entity Path <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="entity_path"
                    placeholder="e.g., purchasing.orders"
                    {...entityForm.register('entity_path')}
                    className="font-mono"
                  />
                  {entityForm.formState.errors.entity_path && (
                    <p className="text-sm text-destructive">
                      {entityForm.formState.errors.entity_path.message}
                    </p>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="entity_description">
                  Description <span className="text-destructive">*</span>
                </Label>
                <Textarea
                  id="entity_description"
                  placeholder="Describe this entity..."
                  {...entityForm.register('description')}
                  className="min-h-[100px]"
                />
                {entityForm.formState.errors.description && (
                  <p className="text-sm text-destructive">
                    {entityForm.formState.errors.description.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="business_purpose">Business Purpose</Label>
                <Textarea
                  id="business_purpose"
                  placeholder="Explain the business purpose of this entity..."
                  {...entityForm.register('business_purpose')}
                  className="min-h-[80px]"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="parent_entity">Parent Entity</Label>
                <Input
                  id="parent_entity"
                  placeholder="e.g., Order"
                  {...entityForm.register('parent_entity')}
                  className="font-mono"
                />
              </div>

              <div className="space-y-2">
                <Label>Child Entities</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Add a child entity..."
                    value={childEntityInput}
                    onChange={(e) => setChildEntityInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addChildEntity()
                      }
                    }}
                    className="font-mono"
                  />
                  <Button type="button" variant="secondary" onClick={addChildEntity}>
                    Add
                  </Button>
                </div>
                {childEntities.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {childEntities.map((child) => (
                      <Badge key={child} variant="outline" className="gap-1 font-mono">
                        {child}
                        <button
                          type="button"
                          onClick={() => removeChildEntity(child)}
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
                <div className="flex items-center justify-between">
                  <Label>Key Attributes</Label>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => appendAttribute({ name: '', type: '', description: '' })}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Add Attribute
                  </Button>
                </div>
                {attributeFields.length > 0 && (
                  <div className="space-y-3 mt-2">
                    {attributeFields.map((field, index) => (
                      <div key={field.id} className="flex gap-2 items-start p-3 rounded-lg border">
                        <div className="flex-1 grid grid-cols-3 gap-2">
                          <Input
                            placeholder="Name"
                            {...entityForm.register(`key_attributes.${index}.name`)}
                            className="font-mono"
                          />
                          <Input
                            placeholder="Type"
                            {...entityForm.register(`key_attributes.${index}.type`)}
                          />
                          <Input
                            placeholder="Description"
                            {...entityForm.register(`key_attributes.${index}.description`)}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeAttribute(index)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label>Common Queries</Label>
                <div className="flex gap-2">
                  <Input
                    placeholder="Add a common query pattern..."
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addCommonQuery()
                      }
                    }}
                  />
                  <Button type="button" variant="secondary" onClick={addCommonQuery}>
                    Add
                  </Button>
                </div>
                {commonQueries.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {commonQueries.map((query, index) => (
                      <li key={index} className="flex items-center gap-2 text-sm">
                        <span className="flex-1">{query}</span>
                        <button
                          type="button"
                          onClick={() => removeCommonQuery(query)}
                          className="text-muted-foreground hover:text-destructive"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Status</Label>
                  <Select
                    value={entityForm.watch('status')}
                    onValueChange={(value: EntityFormData['status']) =>
                      entityForm.setValue('status', value, { shouldDirty: true })
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
                    value={entityForm.watch('visibility')}
                    onValueChange={(value: EntityFormData['visibility']) =>
                      entityForm.setValue('visibility', value, { shouldDirty: true })
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
                        addEntityTag()
                      }
                    }}
                  />
                  <Button type="button" variant="secondary" onClick={addEntityTag}>
                    Add
                  </Button>
                </div>
                {entityTags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {entityTags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="gap-1">
                        {tag}
                        <button
                          type="button"
                          onClick={() => removeEntityTag(tag)}
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
          )}
        </div>

        <DialogFooter className="pt-4 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={isConcept ? conceptForm.handleSubmit(handleConceptSubmit) : entityForm.handleSubmit(handleEntitySubmit)}
            disabled={isSubmitting || (isEditing && !(isConcept ? conceptForm.formState.isDirty : entityForm.formState.isDirty))}
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEditing ? 'Save Changes' : `Create ${nodeTypeLabel}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
