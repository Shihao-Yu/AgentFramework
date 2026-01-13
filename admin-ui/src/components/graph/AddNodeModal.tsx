import { useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Trash2, X } from 'lucide-react'

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
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Checkbox } from '@/components/ui/checkbox'

import {
  NodeType,
  NodeTypeLabels,
  NodeTypeConfig,
  Visibility,
  NodeStatus,
  type CreateNodeRequest,
  type NodeContent,
  type FAQContent,
  type PlaybookContent,
  type PlaybookStep,
  type PermissionRuleContent,
  type PermissionRule,
  type EntityContent,
  type EntityAttribute,
  type SchemaIndexContent,
  type SchemaFieldContent,
  type ExampleContent,
  type ConceptContent,
} from '@/types/graph'

const ALL_NODE_TYPES = Object.values(NodeType) as NodeType[]

const baseFormSchema = z.object({
  node_type: z.enum(['faq', 'playbook', 'permission_rule', 'schema_index', 'schema_field', 'example', 'entity', 'concept']),
  title: z.string().min(3, 'Title must be at least 3 characters'),
  summary: z.string().optional(),
  tags: z.array(z.string()),
  visibility: z.enum(['public', 'internal', 'restricted']),
  status: z.enum(['draft', 'published', 'archived']),
  dataset_name: z.string().optional(),
  field_path: z.string().optional(),
  data_type: z.string().optional(),
})

type BaseFormData = z.infer<typeof baseFormSchema>

interface AddNodeModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: CreateNodeRequest) => Promise<void>
  tenantId: string
  connectToNodeId?: number
  connectToNodeTitle?: string
}

function getDefaultContent(nodeType: NodeType): NodeContent {
  switch (nodeType) {
    case NodeType.FAQ:
      return { question: '', answer: '', variants: [] } as FAQContent
    case NodeType.PLAYBOOK:
      return { description: '', steps: [{ order: 1, action: '' }], prerequisites: [], estimated_time: '', related_forms: [] } as PlaybookContent
    case NodeType.PERMISSION_RULE:
      return { feature: '', description: '', rules: [{ role: '', action: '' }], escalation_path: [] } as PermissionRuleContent
    case NodeType.ENTITY:
      return { entity_name: '', entity_path: '', description: '', business_purpose: '', key_attributes: [], common_operations: [], common_queries: [] } as EntityContent
    case NodeType.SCHEMA_INDEX:
      return { source_type: 'postgres', description: '', table_name: '', primary_key: [], query_patterns: [] } as SchemaIndexContent
    case NodeType.SCHEMA_FIELD:
      return { description: '', business_meaning: '', allowed_values: [], nullable: true, indexed: false } as SchemaFieldContent
    case NodeType.EXAMPLE:
      return { question: '', query: '', query_type: 'postgres', explanation: '', complexity: 'medium' } as ExampleContent
    case NodeType.CONCEPT:
      return { description: '', aliases: [], scope: '', key_questions: [] } as ConceptContent
  }
}

export function AddNodeModal({
  open,
  onOpenChange,
  onSubmit,
  tenantId,
  connectToNodeId,
  connectToNodeTitle,
}: AddNodeModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [content, setContent] = useState<NodeContent>(getDefaultContent(NodeType.FAQ))

  const form = useForm<BaseFormData>({
    resolver: zodResolver(baseFormSchema),
    defaultValues: {
      node_type: 'faq',
      title: '',
      summary: '',
      tags: [],
      visibility: 'internal',
      status: 'draft',
      dataset_name: '',
      field_path: '',
      data_type: '',
    },
  })

  const selectedNodeType = form.watch('node_type') as NodeType
  const tags = form.watch('tags')

  const handleNodeTypeChange = useCallback((value: NodeType) => {
    form.setValue('node_type', value)
    setContent(getDefaultContent(value))
  }, [form])

  const handleAddTag = useCallback(() => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      form.setValue('tags', [...tags, tagInput.trim()])
      setTagInput('')
    }
  }, [tagInput, tags, form])

  const handleRemoveTag = useCallback((tag: string) => {
    form.setValue('tags', tags.filter(t => t !== tag))
  }, [tags, form])

  const handleSubmit = async (data: BaseFormData) => {
    setIsSubmitting(true)
    try {
      const request: CreateNodeRequest = {
        tenant_id: tenantId,
        node_type: data.node_type as NodeType,
        title: data.title,
        summary: data.summary,
        content,
        tags: data.tags,
        visibility: data.visibility as Visibility,
        status: data.status as NodeStatus,
        dataset_name: data.dataset_name || undefined,
        field_path: data.field_path || undefined,
        data_type: data.data_type || undefined,
      }
      await onSubmit(request)
      form.reset()
      setContent(getDefaultContent(NodeType.FAQ))
      setTagInput('')
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  const isSchemaNode = selectedNodeType === NodeType.SCHEMA_INDEX || 
                       selectedNodeType === NodeType.SCHEMA_FIELD || 
                       selectedNodeType === NodeType.EXAMPLE

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[85vh] flex flex-col gap-0">
        <DialogHeader className="pb-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            <span>{NodeTypeConfig[selectedNodeType].icon}</span>
            Add New Node
          </DialogTitle>
          <DialogDescription>
            Create a new knowledge node in the graph.
            {connectToNodeId && (
              <span className="block mt-1 text-primary">
                Will be connected to: <strong>{connectToNodeTitle}</strong>
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4 pr-2">
        <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label>Node Type</Label>
            <Select
              value={selectedNodeType}
              onValueChange={(v) => handleNodeTypeChange(v as NodeType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ALL_NODE_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    <span className="flex items-center gap-2">
                      <span>{NodeTypeConfig[type].icon}</span>
                      <span>{NodeTypeLabels[type]}</span>
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="title">Title *</Label>
            <Input
              id="title"
              {...form.register('title')}
              placeholder="Enter node title..."
            />
            {form.formState.errors.title && (
              <p className="text-sm text-destructive">{form.formState.errors.title.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="summary">Summary</Label>
            <Textarea
              id="summary"
              {...form.register('summary')}
              placeholder="Brief summary of this node..."
              rows={2}
            />
          </div>

          {isSchemaNode && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="dataset_name">Dataset Name</Label>
                <Input
                  id="dataset_name"
                  {...form.register('dataset_name')}
                  placeholder="e.g., orders, products"
                />
              </div>
              {selectedNodeType === NodeType.SCHEMA_FIELD && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="field_path">Field Path</Label>
                    <Input
                      id="field_path"
                      {...form.register('field_path')}
                      placeholder="e.g., orders.status"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="data_type">Data Type</Label>
                    <Input
                      id="data_type"
                      {...form.register('data_type')}
                      placeholder="e.g., varchar(50)"
                    />
                  </div>
                </>
              )}
            </div>
          )}

          <Separator />

          <div className="space-y-4">
            <Label className="text-base font-semibold">Content</Label>
            <ContentForm
              nodeType={selectedNodeType}
              content={content}
              onChange={setContent}
            />
          </div>

          <Separator />

          <div className="space-y-2">
            <Label>Tags</Label>
            <div className="flex gap-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                placeholder="Add a tag..."
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    handleAddTag()
                  }
                }}
              />
              <Button type="button" variant="outline" onClick={handleAddTag}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="gap-1">
                    {tag}
                    <button
                      type="button"
                      onClick={() => handleRemoveTag(tag)}
                      className="hover:text-destructive"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Visibility</Label>
              <Select
                value={form.watch('visibility')}
                onValueChange={(v) => form.setValue('visibility', v as 'public' | 'internal' | 'restricted')}
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
            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={form.watch('status')}
                onValueChange={(v) => form.setValue('status', v as 'draft' | 'published' | 'archived')}
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
          </div>
        </form>
        </div>

        <DialogFooter className="pt-4 border-t">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={form.handleSubmit(handleSubmit)} disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Node'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface ContentFormProps {
  nodeType: NodeType
  content: NodeContent
  onChange: (content: NodeContent) => void
}

function ContentForm({ nodeType, content, onChange }: ContentFormProps) {
  switch (nodeType) {
    case NodeType.FAQ:
      return <FAQContentForm content={content as FAQContent} onChange={onChange} />
    case NodeType.PLAYBOOK:
      return <PlaybookContentForm content={content as PlaybookContent} onChange={onChange} />
    case NodeType.PERMISSION_RULE:
      return <PermissionRuleContentForm content={content as PermissionRuleContent} onChange={onChange} />
    case NodeType.ENTITY:
      return <EntityContentForm content={content as EntityContent} onChange={onChange} />
    case NodeType.SCHEMA_INDEX:
      return <SchemaIndexContentForm content={content as SchemaIndexContent} onChange={onChange} />
    case NodeType.SCHEMA_FIELD:
      return <SchemaFieldContentForm content={content as SchemaFieldContent} onChange={onChange} />
    case NodeType.EXAMPLE:
      return <ExampleContentForm content={content as ExampleContent} onChange={onChange} />
    case NodeType.CONCEPT:
      return <ConceptContentForm content={content as ConceptContent} onChange={onChange} />
  }
}

function FAQContentForm({ content, onChange }: { content: FAQContent; onChange: (c: NodeContent) => void }) {
  const [variantInput, setVariantInput] = useState('')

  const addVariant = () => {
    if (variantInput.trim()) {
      onChange({ ...content, variants: [...(content.variants || []), variantInput.trim()] })
      setVariantInput('')
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Question *</Label>
        <Textarea
          value={content.question}
          onChange={(e) => onChange({ ...content, question: e.target.value })}
          placeholder="What is the question?"
          rows={2}
        />
      </div>
      <div className="space-y-2">
        <Label>Answer *</Label>
        <Textarea
          value={content.answer}
          onChange={(e) => onChange({ ...content, answer: e.target.value })}
          placeholder="Provide the answer..."
          rows={4}
        />
      </div>
      <div className="space-y-2">
        <Label>Question Variants</Label>
        <div className="flex gap-2">
          <Input
            value={variantInput}
            onChange={(e) => setVariantInput(e.target.value)}
            placeholder="Add alternative phrasing..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addVariant())}
          />
          <Button type="button" variant="outline" size="sm" onClick={addVariant}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {content.variants && content.variants.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {content.variants.map((v, i) => (
              <Badge key={i} variant="outline" className="gap-1">
                {v}
                <button
                  type="button"
                  onClick={() => onChange({ ...content, variants: content.variants?.filter((_, idx) => idx !== i) })}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function PlaybookContentForm({ content, onChange }: { content: PlaybookContent; onChange: (c: NodeContent) => void }) {
  const addStep = () => {
    const newStep: PlaybookStep = { order: content.steps.length + 1, action: '' }
    onChange({ ...content, steps: [...content.steps, newStep] })
  }

  const updateStep = (index: number, field: keyof PlaybookStep, value: string | number) => {
    const steps = [...content.steps]
    steps[index] = { ...steps[index], [field]: value }
    onChange({ ...content, steps })
  }

  const removeStep = (index: number) => {
    const steps = content.steps.filter((_, i) => i !== index).map((s, i) => ({ ...s, order: i + 1 }))
    onChange({ ...content, steps })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Description *</Label>
        <Textarea
          value={content.description}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          placeholder="Describe this playbook..."
          rows={2}
        />
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Steps</Label>
          <Button type="button" variant="outline" size="sm" onClick={addStep}>
            <Plus className="h-4 w-4 mr-1" /> Add Step
          </Button>
        </div>
        <div className="space-y-2">
          {content.steps.map((step, i) => (
            <div key={i} className="flex gap-2 items-start p-2 border rounded-md">
              <span className="text-sm text-muted-foreground w-6 pt-2">{step.order}.</span>
              <div className="flex-1 space-y-2">
                <Input
                  value={step.action}
                  onChange={(e) => updateStep(i, 'action', e.target.value)}
                  placeholder="Action to perform..."
                />
                <div className="grid grid-cols-2 gap-2">
                  <Input
                    value={step.owner || ''}
                    onChange={(e) => updateStep(i, 'owner', e.target.value)}
                    placeholder="Owner (optional)"
                  />
                  <Input
                    value={step.details || ''}
                    onChange={(e) => updateStep(i, 'details', e.target.value)}
                    placeholder="Details (optional)"
                  />
                </div>
              </div>
              <Button type="button" variant="ghost" size="sm" onClick={() => removeStep(i)}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Estimated Time</Label>
          <Input
            value={content.estimated_time || ''}
            onChange={(e) => onChange({ ...content, estimated_time: e.target.value })}
            placeholder="e.g., 2-3 hours"
          />
        </div>
      </div>
    </div>
  )
}

function PermissionRuleContentForm({ content, onChange }: { content: PermissionRuleContent; onChange: (c: NodeContent) => void }) {
  const addRule = () => {
    const newRule: PermissionRule = { role: '', action: '' }
    onChange({ ...content, rules: [...content.rules, newRule] })
  }

  const updateRule = (index: number, field: keyof PermissionRule, value: string) => {
    const rules = [...content.rules]
    rules[index] = { ...rules[index], [field]: value }
    onChange({ ...content, rules })
  }

  const removeRule = (index: number) => {
    onChange({ ...content, rules: content.rules.filter((_, i) => i !== index) })
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Feature *</Label>
          <Input
            value={content.feature}
            onChange={(e) => onChange({ ...content, feature: e.target.value })}
            placeholder="e.g., approve_purchase_order"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Description *</Label>
        <Textarea
          value={content.description}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          placeholder="Describe the permission rules..."
          rows={2}
        />
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Rules</Label>
          <Button type="button" variant="outline" size="sm" onClick={addRule}>
            <Plus className="h-4 w-4 mr-1" /> Add Rule
          </Button>
        </div>
        <div className="space-y-2">
          {content.rules.map((rule, i) => (
            <div key={i} className="flex gap-2 items-center p-2 border rounded-md">
              <Input
                value={rule.role}
                onChange={(e) => updateRule(i, 'role', e.target.value)}
                placeholder="Role"
                className="flex-1"
              />
              <Input
                value={rule.action}
                onChange={(e) => updateRule(i, 'action', e.target.value)}
                placeholder="Action"
                className="flex-1"
              />
              <Button type="button" variant="ghost" size="sm" onClick={() => removeRule(i)}>
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function EntityContentForm({ content, onChange }: { content: EntityContent; onChange: (c: NodeContent) => void }) {
  const addAttribute = () => {
    const newAttr: EntityAttribute = { name: '', type: '', description: '' }
    onChange({ ...content, key_attributes: [...(content.key_attributes || []), newAttr] })
  }

  const updateAttribute = (index: number, field: keyof EntityAttribute, value: string) => {
    const attrs = [...(content.key_attributes || [])]
    attrs[index] = { ...attrs[index], [field]: value }
    onChange({ ...content, key_attributes: attrs })
  }

  const removeAttribute = (index: number) => {
    onChange({ ...content, key_attributes: content.key_attributes?.filter((_, i) => i !== index) })
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Entity Name *</Label>
          <Input
            value={content.entity_name}
            onChange={(e) => onChange({ ...content, entity_name: e.target.value })}
            placeholder="e.g., PurchaseOrder"
          />
        </div>
        <div className="space-y-2">
          <Label>Entity Path *</Label>
          <Input
            value={content.entity_path}
            onChange={(e) => onChange({ ...content, entity_path: e.target.value })}
            placeholder="e.g., PurchaseOrder.Line"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Description *</Label>
        <Textarea
          value={content.description}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          placeholder="Describe this entity..."
          rows={2}
        />
      </div>
      <div className="space-y-2">
        <Label>Business Purpose</Label>
        <Input
          value={content.business_purpose || ''}
          onChange={(e) => onChange({ ...content, business_purpose: e.target.value })}
          placeholder="What business purpose does this entity serve?"
        />
      </div>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Key Attributes</Label>
          <Button type="button" variant="outline" size="sm" onClick={addAttribute}>
            <Plus className="h-4 w-4 mr-1" /> Add Attribute
          </Button>
        </div>
        {content.key_attributes && content.key_attributes.length > 0 && (
          <div className="space-y-2">
            {content.key_attributes.map((attr, i) => (
              <div key={i} className="flex gap-2 items-center p-2 border rounded-md">
                <Input
                  value={attr.name}
                  onChange={(e) => updateAttribute(i, 'name', e.target.value)}
                  placeholder="Name"
                  className="flex-1"
                />
                <Input
                  value={attr.type}
                  onChange={(e) => updateAttribute(i, 'type', e.target.value)}
                  placeholder="Type"
                  className="w-24"
                />
                <Input
                  value={attr.description}
                  onChange={(e) => updateAttribute(i, 'description', e.target.value)}
                  placeholder="Description"
                  className="flex-1"
                />
                <Button type="button" variant="ghost" size="sm" onClick={() => removeAttribute(i)}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SchemaIndexContentForm({ content, onChange }: { content: SchemaIndexContent; onChange: (c: NodeContent) => void }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Source Type *</Label>
          <Select
            value={content.source_type}
            onValueChange={(v) => onChange({ ...content, source_type: v as SchemaIndexContent['source_type'] })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="postgres">PostgreSQL</SelectItem>
              <SelectItem value="opensearch">OpenSearch</SelectItem>
              <SelectItem value="rest_api">REST API</SelectItem>
              <SelectItem value="clickhouse">ClickHouse</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Table Name</Label>
          <Input
            value={content.table_name || ''}
            onChange={(e) => onChange({ ...content, table_name: e.target.value })}
            placeholder="e.g., orders"
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Database</Label>
          <Input
            value={content.database || ''}
            onChange={(e) => onChange({ ...content, database: e.target.value })}
            placeholder="e.g., main_db"
          />
        </div>
        <div className="space-y-2">
          <Label>Schema</Label>
          <Input
            value={content.schema || ''}
            onChange={(e) => onChange({ ...content, schema: e.target.value })}
            placeholder="e.g., public"
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Description *</Label>
        <Textarea
          value={content.description}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          placeholder="Describe this schema/table..."
          rows={2}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Row Count Estimate</Label>
          <Input
            type="number"
            value={content.row_count_estimate || ''}
            onChange={(e) => onChange({ ...content, row_count_estimate: parseInt(e.target.value) || undefined })}
            placeholder="e.g., 1000000"
          />
        </div>
        <div className="space-y-2">
          <Label>Update Frequency</Label>
          <Input
            value={content.update_frequency || ''}
            onChange={(e) => onChange({ ...content, update_frequency: e.target.value })}
            placeholder="e.g., real-time"
          />
        </div>
      </div>
    </div>
  )
}

function SchemaFieldContentForm({ content, onChange }: { content: SchemaFieldContent; onChange: (c: NodeContent) => void }) {
  const [allowedValueInput, setAllowedValueInput] = useState('')

  const addAllowedValue = () => {
    if (allowedValueInput.trim()) {
      onChange({ ...content, allowed_values: [...(content.allowed_values || []), allowedValueInput.trim()] })
      setAllowedValueInput('')
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Description *</Label>
        <Textarea
          value={content.description}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          placeholder="Describe this field..."
          rows={2}
        />
      </div>
      <div className="space-y-2">
        <Label>Business Meaning</Label>
        <Input
          value={content.business_meaning || ''}
          onChange={(e) => onChange({ ...content, business_meaning: e.target.value })}
          placeholder="What does this field mean in business terms?"
        />
      </div>
      <div className="space-y-2">
        <Label>Allowed Values</Label>
        <div className="flex gap-2">
          <Input
            value={allowedValueInput}
            onChange={(e) => setAllowedValueInput(e.target.value)}
            placeholder="Add allowed value..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addAllowedValue())}
          />
          <Button type="button" variant="outline" size="sm" onClick={addAllowedValue}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {content.allowed_values && content.allowed_values.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {content.allowed_values.map((v, i) => (
              <Badge key={i} variant="outline" className="gap-1">
                {v}
                <button
                  type="button"
                  onClick={() => onChange({ ...content, allowed_values: content.allowed_values?.filter((_, idx) => idx !== i) })}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>
      <div className="flex gap-4">
        <div className="flex items-center gap-2">
          <Checkbox
            id="nullable"
            checked={content.nullable}
            onCheckedChange={(checked) => onChange({ ...content, nullable: !!checked })}
          />
          <Label htmlFor="nullable">Nullable</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="indexed"
            checked={content.indexed}
            onCheckedChange={(checked) => onChange({ ...content, indexed: !!checked })}
          />
          <Label htmlFor="indexed">Indexed</Label>
        </div>
      </div>
    </div>
  )
}

function ExampleContentForm({ content, onChange }: { content: ExampleContent; onChange: (c: NodeContent) => void }) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Question *</Label>
        <Textarea
          value={content.question}
          onChange={(e) => onChange({ ...content, question: e.target.value })}
          placeholder="Natural language question..."
          rows={2}
        />
      </div>
      <div className="space-y-2">
        <Label>Query *</Label>
        <Textarea
          value={content.query}
          onChange={(e) => onChange({ ...content, query: e.target.value })}
          placeholder="SQL or API query..."
          rows={4}
          className="font-mono text-sm"
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Query Type *</Label>
          <Select
            value={content.query_type}
            onValueChange={(v) => onChange({ ...content, query_type: v })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="postgres">PostgreSQL</SelectItem>
              <SelectItem value="opensearch">OpenSearch</SelectItem>
              <SelectItem value="rest_api">REST API</SelectItem>
              <SelectItem value="clickhouse">ClickHouse</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Complexity</Label>
          <Select
            value={content.complexity || 'medium'}
            onValueChange={(v) => onChange({ ...content, complexity: v as ExampleContent['complexity'] })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-2">
        <Label>Explanation</Label>
        <Textarea
          value={content.explanation || ''}
          onChange={(e) => onChange({ ...content, explanation: e.target.value })}
          placeholder="Explain how the query works..."
          rows={2}
        />
      </div>
    </div>
  )
}

function ConceptContentForm({ content, onChange }: { content: ConceptContent; onChange: (c: NodeContent) => void }) {
  const [aliasInput, setAliasInput] = useState('')
  const [questionInput, setQuestionInput] = useState('')

  const addAlias = () => {
    if (aliasInput.trim()) {
      onChange({ ...content, aliases: [...(content.aliases || []), aliasInput.trim()] })
      setAliasInput('')
    }
  }

  const addQuestion = () => {
    if (questionInput.trim()) {
      onChange({ ...content, key_questions: [...(content.key_questions || []), questionInput.trim()] })
      setQuestionInput('')
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Description *</Label>
        <Textarea
          value={content.description}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          placeholder="Describe this concept..."
          rows={3}
        />
      </div>
      <div className="space-y-2">
        <Label>Scope</Label>
        <Input
          value={content.scope || ''}
          onChange={(e) => onChange({ ...content, scope: e.target.value })}
          placeholder="What does this concept cover?"
        />
      </div>
      <div className="space-y-2">
        <Label>Aliases</Label>
        <div className="flex gap-2">
          <Input
            value={aliasInput}
            onChange={(e) => setAliasInput(e.target.value)}
            placeholder="Add alias..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addAlias())}
          />
          <Button type="button" variant="outline" size="sm" onClick={addAlias}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {content.aliases && content.aliases.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {content.aliases.map((a, i) => (
              <Badge key={i} variant="outline" className="gap-1">
                {a}
                <button
                  type="button"
                  onClick={() => onChange({ ...content, aliases: content.aliases?.filter((_, idx) => idx !== i) })}
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
            value={questionInput}
            onChange={(e) => setQuestionInput(e.target.value)}
            placeholder="Add key question..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addQuestion())}
          />
          <Button type="button" variant="outline" size="sm" onClick={addQuestion}>
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {content.key_questions && content.key_questions.length > 0 && (
          <div className="space-y-1 mt-2">
            {content.key_questions.map((q, i) => (
              <div key={i} className="flex items-center gap-2 text-sm p-2 bg-muted rounded">
                <span className="flex-1">{q}</span>
                <button
                  type="button"
                  onClick={() => onChange({ ...content, key_questions: content.key_questions?.filter((_, idx) => idx !== i) })}
                  className="hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
