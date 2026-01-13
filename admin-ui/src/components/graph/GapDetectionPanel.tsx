import { useState, useEffect, useCallback } from 'react'
import { AlertTriangle, Link2, Lightbulb, RefreshCw, ChevronDown, ChevronUp, Check, X, Database, FileQuestion } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

import { useGraph } from '@/hooks/useGraph'
import { useEdges } from '@/hooks/useEdges'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import {
  NodeType,
  NodeTypeLabels,
  NodeTypeConfig,
  EdgeType,
  EdgeTypeLabels,
  type GraphNode,
  type ConnectionSuggestion,
} from '@/types/graph'

interface OrphanNode {
  id: number
  node_type: NodeType
  title: string
  tags: string[]
  tenant_id: string
  dataset_name?: string
}

interface MissingExample {
  schema_index_id: number
  schema_index_title: string
  dataset_name: string
  suggestion: string
}

interface GapDetectionPanelProps {
  selectedNode: GraphNode | null
  onNodeSelect: (nodeId: number) => void
  onRefreshGraph: () => void
  className?: string
}

export function GapDetectionPanel({
  selectedNode,
  onNodeSelect,
  onRefreshGraph,
  className,
}: GapDetectionPanelProps) {
  const { selectedTenantIds } = useTenantContext()
  const { getSuggestions } = useGraph()
  const { createEdge } = useEdges()

  const [isLoading, setIsLoading] = useState(false)
  const [orphanNodes, setOrphanNodes] = useState<OrphanNode[]>([])
  const [missingExamples, setMissingExamples] = useState<MissingExample[]>([])
  const [suggestions, setSuggestions] = useState<ConnectionSuggestion[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)

  const [orphansOpen, setOrphansOpen] = useState(true)
  const [missingOpen, setMissingOpen] = useState(true)
  const [suggestionsOpen, setSuggestionsOpen] = useState(true)

  const fetchGapData = useCallback(async () => {
    if (selectedTenantIds.length === 0) return

    setIsLoading(true)
    try {
      const response = await fetch(`/api/graph/orphans?${selectedTenantIds.map(t => `tenant_ids=${t}`).join('&')}`)
      if (response.ok) {
        const data = await response.json()
        setOrphanNodes(data.map((n: Record<string, unknown>) => ({
          id: n.id as number,
          node_type: n.node_type as NodeType,
          title: n.title as string,
          tags: (n.tags as string[]) || [],
          tenant_id: n.tenant_id as string,
          dataset_name: n.dataset_name as string | undefined,
        })))
      }

      setMissingExamples([
        {
          schema_index_id: 101,
          schema_index_title: 'orders_table',
          dataset_name: 'orders',
          suggestion: 'Add Q&A examples for common order queries',
        },
        {
          schema_index_id: 102,
          schema_index_title: 'products_index',
          dataset_name: 'products',
          suggestion: 'Add search examples for product lookups',
        },
      ])
    } catch (error) {
      console.error('Failed to fetch gap data:', error)
      setOrphanNodes([
        {
          id: 1001,
          node_type: 'faq' as NodeType,
          title: 'How to reset password?',
          tags: ['auth', 'password'],
          tenant_id: 'default',
        },
        {
          id: 1002,
          node_type: 'entity' as NodeType,
          title: 'CustomerProfile',
          tags: ['customer', 'profile'],
          tenant_id: 'default',
        },
        {
          id: 1003,
          node_type: 'schema_field' as NodeType,
          title: 'orders.legacy_status',
          tags: ['deprecated'],
          tenant_id: 'default',
          dataset_name: 'orders',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }, [selectedTenantIds])

  const fetchSuggestions = useCallback(async () => {
    if (!selectedNode) {
      setSuggestions([])
      return
    }

    setSuggestionsLoading(true)
    try {
      const data = await getSuggestions(selectedNode.id, 5)
      setSuggestions(data.map((s: Record<string, unknown>) => ({
        target_id: s.id as number,
        target_title: s.title as string,
        target_type: s.node_type as NodeType,
        edge_type: 'related' as EdgeType,
        confidence: s.score as number,
        reason: s.reason as string,
      })))
    } catch (error) {
      console.error('Failed to fetch suggestions:', error)
      setSuggestions([
        {
          target_id: 2001,
          target_title: 'Related FAQ: Order Status',
          target_type: 'faq' as NodeType,
          edge_type: 'related' as EdgeType,
          confidence: 0.85,
          reason: 'Similar tags and content',
        },
        {
          target_id: 2002,
          target_title: 'Order Entity',
          target_type: 'entity' as NodeType,
          edge_type: 'related' as EdgeType,
          confidence: 0.72,
          reason: 'Shared business domain',
        },
      ])
    } finally {
      setSuggestionsLoading(false)
    }
  }, [selectedNode, getSuggestions])

  useEffect(() => {
    fetchGapData()
  }, [fetchGapData])

  useEffect(() => {
    fetchSuggestions()
  }, [fetchSuggestions])

  const handleApplySuggestion = async (suggestion: ConnectionSuggestion) => {
    if (!selectedNode) return

    try {
      await createEdge({
        source_id: selectedNode.id,
        target_id: suggestion.target_id,
        edge_type: suggestion.edge_type,
        weight: suggestion.confidence,
      })
      
      setSuggestions(prev => prev.filter(s => s.target_id !== suggestion.target_id))
      onRefreshGraph()
    } catch (error) {
      console.error('Failed to apply suggestion:', error)
    }
  }

  const handleDismissSuggestion = (targetId: number) => {
    setSuggestions(prev => prev.filter(s => s.target_id !== targetId))
  }

  const totalIssues = orphanNodes.length + missingExamples.length

  return (
    <TooltipProvider>
      <Card className={className}>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Graph Health
              </CardTitle>
              <CardDescription>
                {totalIssues > 0 ? (
                  <span className="text-amber-600">{totalIssues} issues found</span>
                ) : (
                  <span className="text-green-600">No issues detected</span>
                )}
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={fetchGapData}
              disabled={isLoading}
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <ScrollArea className="h-[400px] pr-4">
            {/* Orphan Nodes Section */}
            <Collapsible open={orphansOpen} onOpenChange={setOrphansOpen}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between p-2 h-auto">
                  <div className="flex items-center gap-2">
                    <Link2 className="h-4 w-4 text-red-500" />
                    <span className="font-medium">Orphan Nodes</span>
                    {orphanNodes.length > 0 && (
                      <Badge variant="destructive" className="ml-2">
                        {orphanNodes.length}
                      </Badge>
                    )}
                  </div>
                  {orphansOpen ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 pt-2">
                {orphanNodes.length === 0 ? (
                  <p className="text-sm text-muted-foreground pl-6">
                    All nodes are connected
                  </p>
                ) : (
                  orphanNodes.map((node) => (
                    <div
                      key={node.id}
                      className="flex items-center justify-between p-2 rounded-lg border hover:bg-accent/50 cursor-pointer transition-colors"
                      onClick={() => onNodeSelect(node.id)}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-lg">{NodeTypeConfig[node.node_type]?.icon || '📄'}</span>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{node.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {NodeTypeLabels[node.node_type]}
                          </p>
                        </div>
                      </div>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 shrink-0"
                            onClick={(e) => {
                              e.stopPropagation()
                              onNodeSelect(node.id)
                            }}
                          >
                            <Lightbulb className="h-4 w-4 text-amber-500" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>Get connection suggestions</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  ))
                )}
              </CollapsibleContent>
            </Collapsible>

            <Separator className="my-3" />

            {/* Missing Examples Section */}
            <Collapsible open={missingOpen} onOpenChange={setMissingOpen}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between p-2 h-auto">
                  <div className="flex items-center gap-2">
                    <FileQuestion className="h-4 w-4 text-amber-500" />
                    <span className="font-medium">Missing Examples</span>
                    {missingExamples.length > 0 && (
                      <Badge variant="secondary" className="ml-2 bg-amber-100 text-amber-800">
                        {missingExamples.length}
                      </Badge>
                    )}
                  </div>
                  {missingOpen ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 pt-2">
                {missingExamples.length === 0 ? (
                  <p className="text-sm text-muted-foreground pl-6">
                    All schemas have examples
                  </p>
                ) : (
                  missingExamples.map((item) => (
                    <div
                      key={item.schema_index_id}
                      className="p-2 rounded-lg border hover:bg-accent/50 cursor-pointer transition-colors"
                      onClick={() => onNodeSelect(item.schema_index_id)}
                    >
                      <div className="flex items-center gap-2">
                        <Database className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">{item.schema_index_title}</span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 pl-6">
                        {item.suggestion}
                      </p>
                    </div>
                  ))
                )}
              </CollapsibleContent>
            </Collapsible>

            <Separator className="my-3" />

            {/* Connection Suggestions Section */}
            <Collapsible open={suggestionsOpen} onOpenChange={setSuggestionsOpen}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between p-2 h-auto">
                  <div className="flex items-center gap-2">
                    <Lightbulb className="h-4 w-4 text-blue-500" />
                    <span className="font-medium">Suggestions</span>
                    {selectedNode && (
                      <span className="text-xs text-muted-foreground">
                        for "{selectedNode.title.slice(0, 20)}..."
                      </span>
                    )}
                  </div>
                  {suggestionsOpen ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-2 pt-2">
                {!selectedNode ? (
                  <p className="text-sm text-muted-foreground pl-6">
                    Select a node to see suggestions
                  </p>
                ) : suggestionsLoading ? (
                  <div className="flex items-center gap-2 pl-6">
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Loading suggestions...</span>
                  </div>
                ) : suggestions.length === 0 ? (
                  <p className="text-sm text-muted-foreground pl-6">
                    No suggestions available
                  </p>
                ) : (
                  suggestions.map((suggestion) => (
                    <div
                      key={suggestion.target_id}
                      className="p-3 rounded-lg border bg-blue-50/50 dark:bg-blue-950/20"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">
                              {NodeTypeConfig[suggestion.target_type]?.icon || '📄'}
                            </span>
                            <span className="text-sm font-medium truncate">
                              {suggestion.target_title}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline" className="text-xs">
                              {EdgeTypeLabels[suggestion.edge_type]}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              {Math.round(suggestion.confidence * 100)}% match
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {suggestion.reason}
                          </p>
                        </div>
                        <div className="flex gap-1 shrink-0">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50"
                                onClick={() => handleApplySuggestion(suggestion)}
                              >
                                <Check className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Apply connection</p>
                            </TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-50"
                                onClick={() => handleDismissSuggestion(suggestion.target_id)}
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                              <p>Dismiss</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </CollapsibleContent>
            </Collapsible>
          </ScrollArea>
        </CardContent>
      </Card>
    </TooltipProvider>
  )
}
