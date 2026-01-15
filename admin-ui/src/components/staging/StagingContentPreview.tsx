import type { StagingKnowledgeItem } from '@/types/knowledge'
import { Badge } from '@/components/ui/badge'

interface StagingContentPreviewProps {
  item: StagingKnowledgeItem
}

interface FAQContent {
  answer: string
}

interface PlaybookContent {
  domain?: string
  content?: string
  description?: string
}

interface PermissionContent {
  feature?: string
  description?: string
  permissions?: string[]
  roles?: string[]
}

function FAQPreview({ content }: { content: FAQContent }) {
  return (
    <p className="text-sm text-muted-foreground line-clamp-2">
      {content.answer || 'No answer provided'}
    </p>
  )
}

function PlaybookPreview({ content }: { content: PlaybookContent }) {
  return (
    <div className="space-y-1">
      {content.domain && (
        <Badge variant="outline" className="text-xs">{content.domain}</Badge>
      )}
      <p className="text-sm text-muted-foreground line-clamp-2">
        {content.description || content.content?.slice(0, 150) || 'No description'}
      </p>
    </div>
  )
}

function PermissionPreview({ content }: { content: PermissionContent }) {
  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground line-clamp-2">
        {content.description || content.feature || 'No description'}
      </p>
      {content.permissions && content.permissions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {content.permissions.slice(0, 3).map((perm) => (
            <Badge key={perm} variant="secondary" className="text-xs font-mono">
              {perm}
            </Badge>
          ))}
          {content.permissions.length > 3 && (
            <Badge variant="secondary" className="text-xs">
              +{content.permissions.length - 3} more
            </Badge>
          )}
        </div>
      )}
    </div>
  )
}

function GenericPreview({ content }: { content: Record<string, unknown> }) {
  const preview = Object.entries(content)
    .filter(([_, v]) => typeof v === 'string')
    .slice(0, 1)
    .map(([_, v]) => String(v).slice(0, 150))
    .join(' ')
  
  return (
    <p className="text-sm text-muted-foreground line-clamp-2">
      {preview || 'No preview available'}
    </p>
  )
}

export function StagingContentPreview({ item }: StagingContentPreviewProps) {
  const content = item.content

  switch (item.node_type) {
    case 'faq':
      return <FAQPreview content={content as FAQContent} />
    case 'playbook':
      return <PlaybookPreview content={content as PlaybookContent} />
    case 'permission_rule':
      return <PermissionPreview content={content as PermissionContent} />
    default:
      return <GenericPreview content={content} />
  }
}

export function getNodeTypeLabel(nodeType: string): string {
  const labels: Record<string, string> = {
    faq: 'FAQ',
    playbook: 'Playbook',
    permission_rule: 'Permission',
    schema_index: 'Schema',
    schema_field: 'Field',
    example: 'Example',
    entity: 'Entity',
    concept: 'Concept',
  }
  return labels[nodeType] || nodeType
}

export function getNodeTypeBadgeColor(nodeType: string): string {
  const colors: Record<string, string> = {
    faq: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    playbook: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    permission_rule: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
    schema_index: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    example: 'bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200',
  }
  return colors[nodeType] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
}
