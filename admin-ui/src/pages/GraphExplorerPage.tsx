import { useState, useCallback, useEffect, useMemo } from 'react'
import { Network, Search, Filter, Plus, RefreshCw, AlertTriangle } from 'lucide-react'
import { ReactFlowProvider } from '@xyflow/react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { GraphCanvas } from '@/components/graph/GraphCanvas'
import { AddNodeModal } from '@/components/graph/AddNodeModal'
import { AddEdgeDialog } from '@/components/graph/AddEdgeDialog'
import { GapDetectionPanel } from '@/components/graph/GapDetectionPanel'
import { useGraph } from '@/hooks/useGraph'
import { useNodes } from '@/hooks/useNodes'
import { useEdges } from '@/hooks/useEdges'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import { NodeType, NodeTypeLabels, NodeTypeConfig, EdgeType, EdgeTypeLabels, type CreateNodeRequest, type CreateEdgeRequest } from '@/types/graph'

const ALL_NODE_TYPES = Object.values(NodeType) as NodeType[]
const ALL_EDGE_TYPES = Object.values(EdgeType) as EdgeType[]

export function GraphExplorerPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedNodeTypes, setSelectedNodeTypes] = useState<NodeType[]>(ALL_NODE_TYPES)
  const [selectedEdgeTypes, setSelectedEdgeTypes] = useState<EdgeType[]>(ALL_EDGE_TYPES)
  const [depth, setDepth] = useState(2)
  const [hasLoaded, setHasLoaded] = useState(false)
  const [rightPanelTab, setRightPanelTab] = useState<'filters' | 'health'>('filters')
  
  const [addNodeModalOpen, setAddNodeModalOpen] = useState(false)
  const [addEdgeDialogOpen, setAddEdgeDialogOpen] = useState(false)
  const [edgeCreationMode, setEdgeCreationMode] = useState(false)
  const [pendingEdgeSource, setPendingEdgeSource] = useState<number | null>(null)
  const [pendingEdgeTarget, setPendingEdgeTarget] = useState<number | null>(null)

  const { selectedTenantIds } = useTenantContext()
  const { nodes, edges, searchMatches, selectedNode, isLoading, search, selectNode, expand } = useGraph()
  const { createNode } = useNodes()
  const { createEdge } = useEdges()

  const loadAllNodes = useCallback(async () => {
    await search({
      query: '',
      tenant_ids: selectedTenantIds,
      node_types: selectedNodeTypes,
      depth: 3,
      limit: 100,
      include_implicit: true,
    })
    setHasLoaded(true)
  }, [selectedTenantIds, selectedNodeTypes, search])

  useEffect(() => {
    if (!hasLoaded && selectedTenantIds.length > 0) {
      loadAllNodes()
    }
  }, [hasLoaded, selectedTenantIds, loadAllNodes])

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return
    
    await search({
      query: searchQuery,
      tenant_ids: selectedTenantIds,
      node_types: selectedNodeTypes,
      depth,
      include_implicit: selectedEdgeTypes.includes('shared_tag') || selectedEdgeTypes.includes('similar'),
    })
  }, [searchQuery, selectedTenantIds, selectedNodeTypes, depth, selectedEdgeTypes, search])

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }, [handleSearch])

  const handleNodeDoubleClick = useCallback(async (nodeId: number) => {
    await expand(nodeId, depth)
  }, [expand, depth])

  const toggleNodeType = useCallback((nodeType: NodeType) => {
    setSelectedNodeTypes(prev => 
      prev.includes(nodeType)
        ? prev.filter(t => t !== nodeType)
        : [...prev, nodeType]
    )
  }, [])

  const toggleEdgeType = useCallback((edgeType: EdgeType) => {
    setSelectedEdgeTypes(prev => 
      prev.includes(edgeType)
        ? prev.filter(t => t !== edgeType)
        : [...prev, edgeType]
    )
  }, [])

  const filteredEdges = edges.filter(e => selectedEdgeTypes.includes(e.edge_type))
  const filteredNodes = nodes.filter(n => selectedNodeTypes.includes(n.node_type))

  const pendingSourceNode = useMemo(() => 
    nodes.find(n => n.id === pendingEdgeSource) || null,
    [nodes, pendingEdgeSource]
  )
  
  const pendingTargetNode = useMemo(() => 
    nodes.find(n => n.id === pendingEdgeTarget) || null,
    [nodes, pendingEdgeTarget]
  )

  const handleCreateNode = useCallback(async (data: CreateNodeRequest) => {
    await createNode(data)
    await loadAllNodes()
  }, [createNode, loadAllNodes])

  const handleEdgeCreate = useCallback((sourceId: number, targetId: number) => {
    setPendingEdgeSource(sourceId)
    setPendingEdgeTarget(targetId)
    setAddEdgeDialogOpen(true)
  }, [])

  const handleCreateEdge = useCallback(async (data: CreateEdgeRequest) => {
    await createEdge(data)
    setPendingEdgeSource(null)
    setPendingEdgeTarget(null)
    setEdgeCreationMode(false)
    await loadAllNodes()
  }, [createEdge, loadAllNodes])

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Knowledge Graph Explorer</h1>
          <p className="text-sm text-muted-foreground">
            Visualize and explore relationships between knowledge nodes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => setAddNodeModalOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add Node
          </Button>
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden">
        <Card className="flex flex-1 flex-col overflow-hidden">
          <CardHeader className="shrink-0 pb-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search nodes..."
                  className="pl-9"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={handleKeyPress}
                />
              </div>
              <Button onClick={handleSearch} disabled={isLoading}>
                {isLoading ? 'Searching...' : 'Search'}
              </Button>
              <Button variant="outline" onClick={loadAllNodes} disabled={isLoading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
                Load All
              </Button>
            </div>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden p-0">
            {nodes.length > 0 ? (
              <ReactFlowProvider>
                <GraphCanvas
                  graphNodes={filteredNodes}
                  graphEdges={filteredEdges}
                  searchMatches={searchMatches}
                  onNodeSelect={selectNode}
                  onNodeDoubleClick={handleNodeDoubleClick}
                  edgeCreationMode={edgeCreationMode}
                  onEdgeCreationModeChange={setEdgeCreationMode}
                  pendingEdgeSource={pendingEdgeSource}
                  onPendingEdgeSourceChange={setPendingEdgeSource}
                  onEdgeCreate={handleEdgeCreate}
                  className="h-full w-full"
                />
              </ReactFlowProvider>
            ) : (
              <div className="flex h-full items-center justify-center">
                <div className="text-center">
                  <Network className="mx-auto h-12 w-12 text-muted-foreground/50" />
                  <h3 className="mt-4 text-lg font-medium">No nodes to display</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Search for nodes or select a tenant to begin exploring
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto">
          <Tabs value={rightPanelTab} onValueChange={(v) => setRightPanelTab(v as 'filters' | 'health')}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="filters" className="flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Filters
              </TabsTrigger>
              <TabsTrigger value="health" className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                Health
              </TabsTrigger>
            </TabsList>

            <TabsContent value="filters" className="space-y-4 mt-4">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Node Types</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {ALL_NODE_TYPES.map((type) => {
                    const config = NodeTypeConfig[type]
                    return (
                      <div key={type} className="flex items-center gap-2">
                        <Checkbox
                          id={`node-${type}`}
                          checked={selectedNodeTypes.includes(type)}
                          onCheckedChange={() => toggleNodeType(type)}
                        />
                        <Label
                          htmlFor={`node-${type}`}
                          className="flex items-center gap-2 text-sm font-normal"
                        >
                          <span>{config.icon}</span>
                          <span>{NodeTypeLabels[type]}</span>
                        </Label>
                      </div>
                    )
                  })}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Edge Types</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {ALL_EDGE_TYPES.map((type) => (
                    <div key={type} className="flex items-center gap-2">
                      <Checkbox
                        id={`edge-${type}`}
                        checked={selectedEdgeTypes.includes(type)}
                        onCheckedChange={() => toggleEdgeType(type)}
                      />
                      <Label
                        htmlFor={`edge-${type}`}
                        className="text-sm font-normal"
                      >
                        {EdgeTypeLabels[type]}
                      </Label>
                    </div>
                  ))}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Expansion Depth</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2">
                    {[1, 2, 3, 4, 5].map((d) => (
                      <Button
                        key={d}
                        variant={depth === d ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => setDepth(d)}
                      >
                        {d}
                      </Button>
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Hops from search results
                  </p>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="health" className="mt-4">
              <GapDetectionPanel
                selectedNode={selectedNode}
                onNodeSelect={selectNode}
                onRefreshGraph={loadAllNodes}
              />
            </TabsContent>
          </Tabs>

          {selectedNode && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <span>{NodeTypeConfig[selectedNode.node_type].icon}</span>
                  Selected Node
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <p className="text-sm font-medium">{selectedNode.title}</p>
                  <Badge variant="outline" className="mt-1">
                    {NodeTypeLabels[selectedNode.node_type]}
                  </Badge>
                </div>
                {selectedNode.summary && (
                  <p className="text-sm text-muted-foreground">{selectedNode.summary}</p>
                )}
                <div className="flex flex-wrap gap-1">
                  {selectedNode.tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2 pt-2">
                  <Button variant="outline" size="sm" className="flex-1">
                    View Details
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1">
                    Edit
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Graph Stats</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Nodes:</span>
                  <span className="font-medium">{filteredNodes.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Edges:</span>
                  <span className="font-medium">{filteredEdges.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Search Matches:</span>
                  <span className="font-medium">{searchMatches.length}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <AddNodeModal
        open={addNodeModalOpen}
        onOpenChange={setAddNodeModalOpen}
        onSubmit={handleCreateNode}
        tenantId={selectedTenantIds[0] || 'default'}
        connectToNodeId={selectedNode?.id}
        connectToNodeTitle={selectedNode?.title}
      />

      <AddEdgeDialog
        open={addEdgeDialogOpen}
        onOpenChange={(open) => {
          setAddEdgeDialogOpen(open)
          if (!open) {
            setPendingEdgeSource(null)
            setPendingEdgeTarget(null)
          }
        }}
        onSubmit={handleCreateEdge}
        sourceNode={pendingSourceNode}
        targetNode={pendingTargetNode}
      />
    </div>
  )
}
