import { ArrowLeft, Pencil, Trash2, Network, History } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { VersionHistoryPanel } from './VersionHistoryPanel'

import type {
  KnowledgeNode,
  KnowledgeEdge,
  FAQContent,
  PlaybookContent,
  EntityContent,
  ConceptContent,
  SchemaIndexContent,
  SchemaFieldContent,
  ExampleContent,
  PermissionRuleContent,
} from '@/types/graph'
import { NodeTypeLabels, NodeTypeConfig, EdgeTypeLabels } from '@/types/graph'

interface NodeDetailProps {
  node: KnowledgeNode
  edges?: KnowledgeEdge[]
  relatedNodes?: KnowledgeNode[]
  onBack?: () => void
  onEdit?: () => void
  onDelete?: () => void
  onViewInGraph?: () => void
  onRollback?: (version: number) => Promise<void>
}

function FAQContentView({ content }: { content: FAQContent }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Question</h4>
        <p className="mt-1">{content.question}</p>
      </div>
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Answer</h4>
        <div className="mt-1 prose prose-sm dark:prose-invert max-w-none">
          {content.answer}
        </div>
      </div>
      {content.variants && content.variants.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Variants</h4>
          <ul className="mt-1 list-disc list-inside space-y-1 text-sm">
            {content.variants.map((variant, index) => (
              <li key={index}>{variant}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function PlaybookContentView({ content }: { content: PlaybookContent }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
        <p className="mt-1">{content.description}</p>
      </div>
      {content.prerequisites && content.prerequisites.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Prerequisites</h4>
          <ul className="mt-1 list-disc list-inside space-y-1 text-sm">
            {content.prerequisites.map((prereq, index) => (
              <li key={index}>{prereq}</li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Steps</h4>
        <ol className="mt-2 space-y-3">
          {content.steps.map((step) => (
            <li key={step.order} className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                {step.order}
              </span>
              <div className="flex-1">
                <p className="font-medium">{step.action}</p>
                {step.owner && (
                  <p className="text-sm text-muted-foreground">Owner: {step.owner}</p>
                )}
                {step.details && (
                  <p className="text-sm text-muted-foreground">{step.details}</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
      {content.estimated_time && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Estimated Time</h4>
          <p className="mt-1">{content.estimated_time}</p>
        </div>
      )}
    </div>
  )
}

function EntityContentView({ content }: { content: EntityContent }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Entity Name</h4>
          <p className="mt-1 font-mono">{content.entity_name}</p>
        </div>
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Entity Path</h4>
          <p className="mt-1 font-mono">{content.entity_path}</p>
        </div>
      </div>
      {content.parent_entity && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Parent Entity</h4>
          <p className="mt-1 font-mono">{content.parent_entity}</p>
        </div>
      )}
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
        <p className="mt-1">{content.description}</p>
      </div>
      {content.business_purpose && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Business Purpose</h4>
          <p className="mt-1">{content.business_purpose}</p>
        </div>
      )}
      {content.key_attributes && content.key_attributes.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Key Attributes</h4>
          <div className="mt-2 rounded-lg border">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-3 py-2 text-left text-xs font-medium">Name</th>
                  <th className="px-3 py-2 text-left text-xs font-medium">Type</th>
                  <th className="px-3 py-2 text-left text-xs font-medium">Description</th>
                </tr>
              </thead>
              <tbody>
                {content.key_attributes.map((attr, index) => (
                  <tr key={index} className="border-b last:border-0">
                    <td className="px-3 py-2 font-mono text-sm">{attr.name}</td>
                    <td className="px-3 py-2 text-sm">{attr.type}</td>
                    <td className="px-3 py-2 text-sm text-muted-foreground">{attr.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {content.child_entities && content.child_entities.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Child Entities</h4>
          <div className="mt-1 flex flex-wrap gap-1">
            {content.child_entities.map((child) => (
              <Badge key={child} variant="outline" className="font-mono">
                {child}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ConceptContentView({ content }: { content: ConceptContent }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
        <p className="mt-1">{content.description}</p>
      </div>
      {content.aliases && content.aliases.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Aliases</h4>
          <div className="mt-1 flex flex-wrap gap-1">
            {content.aliases.map((alias) => (
              <Badge key={alias} variant="secondary">
                {alias}
              </Badge>
            ))}
          </div>
        </div>
      )}
      {content.scope && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Scope</h4>
          <p className="mt-1">{content.scope}</p>
        </div>
      )}
      {content.key_questions && content.key_questions.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Key Questions</h4>
          <ul className="mt-1 list-disc list-inside space-y-1 text-sm">
            {content.key_questions.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function SchemaIndexContentView({ content }: { content: SchemaIndexContent }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Source Type</h4>
          <Badge variant="outline" className="mt-1">{content.source_type}</Badge>
        </div>
        {content.table_name && (
          <div>
            <h4 className="text-sm font-medium text-muted-foreground">Table Name</h4>
            <p className="mt-1 font-mono">{content.table_name}</p>
          </div>
        )}
      </div>
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
        <p className="mt-1">{content.description}</p>
      </div>
      {content.primary_key && content.primary_key.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Primary Key</h4>
          <p className="mt-1 font-mono">{content.primary_key.join(', ')}</p>
        </div>
      )}
      {content.query_patterns && content.query_patterns.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Query Patterns</h4>
          <ul className="mt-1 list-disc list-inside space-y-1 text-sm">
            {content.query_patterns.map((pattern, index) => (
              <li key={index}>{pattern}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function SchemaFieldContentView({ content }: { content: SchemaFieldContent }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
        <p className="mt-1">{content.description}</p>
      </div>
      {content.business_meaning && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Business Meaning</h4>
          <p className="mt-1">{content.business_meaning}</p>
        </div>
      )}
      {content.allowed_values && content.allowed_values.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Allowed Values</h4>
          <div className="mt-1 flex flex-wrap gap-1">
            {content.allowed_values.map((value) => (
              <Badge key={value} variant="outline" className="font-mono">
                {value}
              </Badge>
            ))}
          </div>
        </div>
      )}
      <div className="flex gap-4">
        <Badge variant={content.nullable ? 'secondary' : 'default'}>
          {content.nullable ? 'Nullable' : 'Required'}
        </Badge>
        {content.indexed && <Badge>Indexed</Badge>}
      </div>
    </div>
  )
}

function ExampleContentView({ content }: { content: ExampleContent }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Question</h4>
        <p className="mt-1">{content.question}</p>
      </div>
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Query ({content.query_type})</h4>
        <pre className="mt-1 rounded-lg bg-muted p-3 text-sm font-mono overflow-x-auto">
          {content.query}
        </pre>
      </div>
      {content.explanation && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Explanation</h4>
          <p className="mt-1">{content.explanation}</p>
        </div>
      )}
      <div className="flex gap-2">
        {content.complexity && <Badge variant="outline">Complexity: {content.complexity}</Badge>}
        {content.verified && <Badge variant="default">Verified</Badge>}
      </div>
    </div>
  )
}

function PermissionRuleContentView({ content }: { content: PermissionRuleContent }) {
  return (
    <div className="space-y-4">
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Feature</h4>
        <p className="mt-1 font-mono">{content.feature}</p>
      </div>
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Description</h4>
        <p className="mt-1">{content.description}</p>
      </div>
      <div>
        <h4 className="text-sm font-medium text-muted-foreground">Rules</h4>
        <div className="mt-2 rounded-lg border">
          <table className="w-full">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-3 py-2 text-left text-xs font-medium">Role</th>
                <th className="px-3 py-2 text-left text-xs font-medium">Action</th>
                <th className="px-3 py-2 text-left text-xs font-medium">Constraint</th>
              </tr>
            </thead>
            <tbody>
              {content.rules.map((rule, index) => (
                <tr key={index} className="border-b last:border-0">
                  <td className="px-3 py-2 text-sm">{rule.role}</td>
                  <td className="px-3 py-2 text-sm">{rule.action}</td>
                  <td className="px-3 py-2 text-sm font-mono text-muted-foreground">
                    {rule.constraint ? JSON.stringify(rule.constraint) : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {content.escalation_path && content.escalation_path.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-muted-foreground">Escalation Path</h4>
          <div className="mt-1 flex items-center gap-2">
            {content.escalation_path.map((role, index) => (
              <span key={role} className="flex items-center gap-2">
                <Badge variant="outline">{role}</Badge>
                {index < content.escalation_path!.length - 1 && (
                  <span className="text-muted-foreground">→</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ContentView({ node }: { node: KnowledgeNode }) {
  const content = node.content

  switch (node.node_type) {
    case 'faq':
      return <FAQContentView content={content as FAQContent} />
    case 'playbook':
      return <PlaybookContentView content={content as PlaybookContent} />
    case 'entity':
      return <EntityContentView content={content as EntityContent} />
    case 'concept':
      return <ConceptContentView content={content as ConceptContent} />
    case 'schema_index':
      return <SchemaIndexContentView content={content as SchemaIndexContent} />
    case 'schema_field':
      return <SchemaFieldContentView content={content as SchemaFieldContent} />
    case 'example':
      return <ExampleContentView content={content as ExampleContent} />
    case 'permission_rule':
      return <PermissionRuleContentView content={content as PermissionRuleContent} />
    default:
      return (
        <pre className="rounded-lg bg-muted p-4 text-sm overflow-x-auto">
          {JSON.stringify(content, null, 2)}
        </pre>
      )
  }
}

export function NodeDetail({
  node,
  edges = [],
  relatedNodes = [],
  onBack,
  onEdit,
  onDelete,
  onViewInGraph,
  onRollback,
}: NodeDetailProps) {
  const config = NodeTypeConfig[node.node_type]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {onBack && (
            <Button variant="ghost" size="icon" onClick={onBack}>
              <ArrowLeft className="h-4 w-4" />
            </Button>
          )}
          <div className="flex items-center gap-3">
            <span className="text-3xl">{config.icon}</span>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{node.title}</h1>
              <div className="flex items-center gap-2 mt-1">
                <Badge
                  variant="outline"
                  style={{ borderColor: config.color, color: config.color }}
                >
                  {NodeTypeLabels[node.node_type]}
                </Badge>
                <Badge variant={node.status === 'published' ? 'default' : 'secondary'}>
                  {node.status}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  Tenant: {node.tenant_id}
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onViewInGraph && (
            <Button variant="outline" onClick={onViewInGraph}>
              <Network className="mr-2 h-4 w-4" />
              View in Graph
            </Button>
          )}
          {onEdit && (
            <Button variant="outline" onClick={onEdit}>
              <Pencil className="mr-2 h-4 w-4" />
              Edit
            </Button>
          )}
          {onDelete && (
            <Button variant="outline" className="text-destructive" onClick={onDelete}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          )}
        </div>
      </div>

      <Tabs defaultValue="content" className="w-full">
        <TabsList>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="relationships">
            Relationships ({edges.length})
          </TabsTrigger>
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
          <TabsTrigger value="history">
            <History className="mr-1 h-3 w-3" />
            History
          </TabsTrigger>
        </TabsList>

        <TabsContent value="content" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Content</CardTitle>
              {node.summary && (
                <CardDescription>{node.summary}</CardDescription>
              )}
            </CardHeader>
            <CardContent>
              <ContentView node={node} />
            </CardContent>
          </Card>

          {node.tags.length > 0 && (
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-base">Tags</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {node.tags.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="relationships" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Connected Nodes</CardTitle>
              <CardDescription>
                Relationships with other knowledge nodes
              </CardDescription>
            </CardHeader>
            <CardContent>
              {edges.length === 0 ? (
                <p className="text-sm text-muted-foreground">No relationships defined</p>
              ) : (
                <div className="space-y-3">
                  {edges.map((edge) => {
                    const isSource = edge.source_id === node.id
                    const relatedNodeId = isSource ? edge.target_id : edge.source_id
                    const relatedNode = relatedNodes.find(n => n.id === relatedNodeId)
                    
                    return (
                      <div
                        key={edge.id}
                        className="flex items-center justify-between rounded-lg border p-3"
                      >
                        <div className="flex items-center gap-3">
                          {relatedNode && (
                            <>
                              <span>{NodeTypeConfig[relatedNode.node_type].icon}</span>
                              <div>
                                <p className="font-medium">{relatedNode.title}</p>
                                <p className="text-xs text-muted-foreground">
                                  {NodeTypeLabels[relatedNode.node_type]}
                                </p>
                              </div>
                            </>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">
                            {isSource ? '→' : '←'} {EdgeTypeLabels[edge.edge_type]}
                          </Badge>
                          {edge.is_auto_generated && (
                            <Badge variant="secondary" className="text-xs">
                              Auto
                            </Badge>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metadata" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Metadata</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-muted-foreground">ID</dt>
                  <dd className="font-mono">{node.id}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Tenant</dt>
                  <dd>{node.tenant_id}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Visibility</dt>
                  <dd className="capitalize">{node.visibility}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Status</dt>
                  <dd className="capitalize">{node.status}</dd>
                </div>
                {node.dataset_name && (
                  <div>
                    <dt className="text-muted-foreground">Dataset</dt>
                    <dd className="font-mono">{node.dataset_name}</dd>
                  </div>
                )}
                {node.field_path && (
                  <div>
                    <dt className="text-muted-foreground">Field Path</dt>
                    <dd className="font-mono">{node.field_path}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-muted-foreground">Created</dt>
                  <dd>
                    {new Date(node.created_at).toLocaleString()}
                    {node.created_by && <span className="text-muted-foreground"> by {node.created_by}</span>}
                  </dd>
                </div>
                {node.updated_at && (
                  <div>
                    <dt className="text-muted-foreground">Updated</dt>
                    <dd>
                      {new Date(node.updated_at).toLocaleString()}
                      {node.updated_by && <span className="text-muted-foreground"> by {node.updated_by}</span>}
                    </dd>
                  </div>
                )}
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="mt-4">
          <VersionHistoryPanel
            nodeId={node.id}
            currentVersion={node.version}
            onRollback={onRollback}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
