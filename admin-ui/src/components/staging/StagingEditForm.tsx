import { useState } from 'react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { X } from 'lucide-react'
import type { StagingKnowledgeItem } from '@/types/knowledge'

export interface StagingEditData {
  title: string
  content: Record<string, unknown>
  tags: string[]
}

interface StagingEditFormProps {
  item: StagingKnowledgeItem
  editedData: StagingEditData
  onChange: (data: StagingEditData) => void
}

function FAQEditForm({ 
  content, 
  onChange 
}: { 
  content: { answer?: string }
  onChange: (content: Record<string, unknown>) => void 
}) {
  return (
    <div className="space-y-2">
      <Label>Answer</Label>
      <Textarea
        value={content.answer || ''}
        onChange={(e) => onChange({ ...content, answer: e.target.value })}
        className="min-h-[200px]"
        placeholder="Enter the answer (Markdown supported)..."
      />
    </div>
  )
}

function PlaybookEditForm({ 
  content, 
  onChange 
}: { 
  content: { domain?: string; content?: string; description?: string }
  onChange: (content: Record<string, unknown>) => void 
}) {
  return (
    <>
      <div className="space-y-2">
        <Label>Domain</Label>
        <Input
          value={content.domain || ''}
          onChange={(e) => onChange({ ...content, domain: e.target.value })}
          placeholder="e.g., purchasing, finance"
        />
      </div>
      <div className="space-y-2">
        <Label>Content</Label>
        <Textarea
          value={content.content || ''}
          onChange={(e) => onChange({ ...content, content: e.target.value })}
          className="min-h-[300px] font-mono text-sm"
          placeholder="Playbook content (Markdown supported)..."
        />
      </div>
    </>
  )
}

function PermissionEditForm({ 
  content, 
  onChange 
}: { 
  content: { feature?: string; description?: string; permissions?: string[]; roles?: string[]; context?: string }
  onChange: (content: Record<string, unknown>) => void 
}) {
  const [newPermission, setNewPermission] = useState('')
  const [newRole, setNewRole] = useState('')

  const addPermission = () => {
    if (newPermission.trim()) {
      onChange({ 
        ...content, 
        permissions: [...(content.permissions || []), newPermission.trim()] 
      })
      setNewPermission('')
    }
  }

  const removePermission = (perm: string) => {
    onChange({ 
      ...content, 
      permissions: (content.permissions || []).filter(p => p !== perm) 
    })
  }

  const addRole = () => {
    if (newRole.trim()) {
      onChange({ 
        ...content, 
        roles: [...(content.roles || []), newRole.trim()] 
      })
      setNewRole('')
    }
  }

  const removeRole = (role: string) => {
    onChange({ 
      ...content, 
      roles: (content.roles || []).filter(r => r !== role) 
    })
  }

  return (
    <>
      <div className="space-y-2">
        <Label>Feature Name</Label>
        <Input
          value={content.feature || ''}
          onChange={(e) => onChange({ ...content, feature: e.target.value })}
          placeholder="Feature name..."
        />
      </div>
      <div className="space-y-2">
        <Label>Description</Label>
        <Textarea
          value={content.description || ''}
          onChange={(e) => onChange({ ...content, description: e.target.value })}
          className="min-h-[100px]"
          placeholder="Describe what this feature does..."
        />
      </div>
      <div className="space-y-2">
        <Label>Required Permissions</Label>
        <div className="flex flex-wrap gap-2 mb-2">
          {(content.permissions || []).map((perm) => (
            <Badge key={perm} variant="secondary" className="font-mono">
              {perm}
              <button onClick={() => removePermission(perm)} className="ml-1 hover:text-destructive">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={newPermission}
            onChange={(e) => setNewPermission(e.target.value)}
            placeholder="Add permission..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addPermission())}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Roles with Access</Label>
        <div className="flex flex-wrap gap-2 mb-2">
          {(content.roles || []).map((role) => (
            <Badge key={role} variant="outline">
              {role}
              <button onClick={() => removeRole(role)} className="ml-1 hover:text-destructive">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
            placeholder="Add role..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addRole())}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label>Additional Context (Optional)</Label>
        <Textarea
          value={content.context || ''}
          onChange={(e) => onChange({ ...content, context: e.target.value })}
          className="min-h-[80px]"
          placeholder="Any additional context or notes..."
        />
      </div>
    </>
  )
}

function GenericEditForm({ 
  content, 
  onChange 
}: { 
  content: Record<string, unknown>
  onChange: (content: Record<string, unknown>) => void 
}) {
  return (
    <div className="space-y-2">
      <Label>Content (JSON)</Label>
      <Textarea
        value={JSON.stringify(content, null, 2)}
        onChange={(e) => {
          try {
            onChange(JSON.parse(e.target.value))
          } catch {
            // Invalid JSON, don't update
          }
        }}
        className="min-h-[300px] font-mono text-sm"
        placeholder="Edit content as JSON..."
      />
    </div>
  )
}

export function StagingEditForm({ item, editedData, onChange }: StagingEditFormProps) {
  const handleContentChange = (newContent: Record<string, unknown>) => {
    onChange({ ...editedData, content: newContent })
  }

  const handleTagRemove = (tagToRemove: string) => {
    onChange({ ...editedData, tags: editedData.tags.filter(t => t !== tagToRemove) })
  }

  const [newTag, setNewTag] = useState('')
  const handleAddTag = () => {
    if (newTag.trim() && !editedData.tags.includes(newTag.trim())) {
      onChange({ ...editedData, tags: [...editedData.tags, newTag.trim()] })
      setNewTag('')
    }
  }

  const renderContentForm = () => {
    switch (item.node_type) {
      case 'faq':
        return <FAQEditForm content={editedData.content as { answer?: string }} onChange={handleContentChange} />
      case 'playbook':
        return <PlaybookEditForm content={editedData.content as { domain?: string; content?: string }} onChange={handleContentChange} />
      case 'permission_rule':
        return <PermissionEditForm content={editedData.content as { feature?: string; description?: string; permissions?: string[]; roles?: string[] }} onChange={handleContentChange} />
      default:
        return <GenericEditForm content={editedData.content} onChange={handleContentChange} />
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>{item.node_type === 'faq' ? 'Question' : 'Title'}</Label>
        <Input
          value={editedData.title}
          onChange={(e) => onChange({ ...editedData, title: e.target.value })}
          placeholder={item.node_type === 'faq' ? 'Enter the question...' : 'Enter title...'}
        />
      </div>

      {renderContentForm()}

      <div className="space-y-2">
        <Label>Tags</Label>
        <div className="flex flex-wrap gap-2 mb-2">
          {editedData.tags.map((tag) => (
            <Badge key={tag} variant="secondary">
              {tag}
              <button onClick={() => handleTagRemove(tag)} className="ml-1 hover:text-destructive">
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            placeholder="Add tag..."
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
          />
        </div>
      </div>
    </div>
  )
}
