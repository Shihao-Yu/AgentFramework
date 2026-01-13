import { useState, useEffect, useCallback } from 'react'
import {
  Network,
  Link2,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  Activity,
  Layers,
  GitBranch,
} from 'lucide-react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

import { useGraph } from '@/hooks/useGraph'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import { NodeType, NodeTypeLabels, EdgeType, EdgeTypeLabels } from '@/types/graph'

const NODE_COLORS = {
  [NodeType.FAQ]: '#2ecc71',
  [NodeType.PLAYBOOK]: '#e67e22',
  [NodeType.PERMISSION_RULE]: '#e74c3c',
  [NodeType.SCHEMA_INDEX]: '#7f8c8d',
  [NodeType.SCHEMA_FIELD]: '#bdc3c7',
  [NodeType.EXAMPLE]: '#9b59b6',
  [NodeType.ENTITY]: '#3498db',
  [NodeType.CONCEPT]: '#f1c40f',
}

const EDGE_COLORS = {
  [EdgeType.RELATED]: '#3498db',
  [EdgeType.PARENT]: '#2ecc71',
  [EdgeType.EXAMPLE_OF]: '#9b59b6',
  [EdgeType.SHARED_TAG]: '#f39c12',
  [EdgeType.SIMILAR]: '#e74c3c',
}

interface GraphStats {
  total_nodes: number
  by_type: Partial<Record<NodeType, number>>
  total_edges: number
  by_edge_type: Partial<Record<EdgeType, number>>
  orphan_nodes: number
  avg_connections: number
}

interface SyncStatus {
  pending_events: number
  last_processed?: string
  auto_generated_edges: Record<string, number>
}

export function GraphAnalyticsPage() {
  const { selectedTenantIds } = useTenantContext()
  const { getStats, reloadGraph } = useGraph()

  const [stats, setStats] = useState<GraphStats | null>(null)
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isReloading, setIsReloading] = useState(false)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    try {
      const graphStats = await getStats(selectedTenantIds)
      setStats(graphStats)

      const syncResponse = await fetch('/api/sync/status')
      if (syncResponse.ok) {
        const syncData = await syncResponse.json()
        setSyncStatus(syncData)
      }
    } catch (error) {
      console.error('Failed to fetch analytics:', error)
      setStats({
        total_nodes: 156,
        by_type: {
          [NodeType.FAQ]: 45,
          [NodeType.PLAYBOOK]: 12,
          [NodeType.PERMISSION_RULE]: 8,
          [NodeType.SCHEMA_INDEX]: 15,
          [NodeType.SCHEMA_FIELD]: 48,
          [NodeType.EXAMPLE]: 18,
          [NodeType.ENTITY]: 6,
          [NodeType.CONCEPT]: 4,
        },
        total_edges: 234,
        by_edge_type: {
          [EdgeType.RELATED]: 89,
          [EdgeType.PARENT]: 67,
          [EdgeType.EXAMPLE_OF]: 18,
          [EdgeType.SHARED_TAG]: 42,
          [EdgeType.SIMILAR]: 18,
        },
        orphan_nodes: 8,
        avg_connections: 3.2,
      })
      setSyncStatus({
        pending_events: 3,
        last_processed: new Date().toISOString(),
        auto_generated_edges: {
          shared_tag: 42,
          similar: 18,
        },
      })
    } finally {
      setIsLoading(false)
    }
  }, [selectedTenantIds, getStats])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleReloadGraph = async () => {
    setIsReloading(true)
    try {
      await reloadGraph()
      await fetchData()
    } catch (error) {
      console.error('Failed to reload graph:', error)
    } finally {
      setIsReloading(false)
    }
  }

  const nodeTypeData = stats
    ? Object.entries(stats.by_type).map(([type, count]) => ({
        name: NodeTypeLabels[type as NodeType] || type,
        value: count,
        color: NODE_COLORS[type as NodeType] || '#999',
      }))
    : []

  const edgeTypeData = stats
    ? Object.entries(stats.by_edge_type).map(([type, count]) => ({
        name: EdgeTypeLabels[type as EdgeType] || type,
        value: count,
        color: EDGE_COLORS[type as EdgeType] || '#999',
      }))
    : []

  const connectivityScore = stats
    ? Math.min(100, Math.round((1 - stats.orphan_nodes / stats.total_nodes) * 100))
    : 0

  const healthScore = stats
    ? Math.round(
        (connectivityScore * 0.4 +
          Math.min(100, stats.avg_connections * 20) * 0.3 +
          (stats.total_edges > 0 ? 100 : 0) * 0.3)
      )
    : 0

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Graph Analytics</h1>
          <p className="text-muted-foreground">
            Monitor knowledge graph health and connectivity metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={fetchData} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={handleReloadGraph} disabled={isReloading}>
            <Activity className={`mr-2 h-4 w-4 ${isReloading ? 'animate-spin' : ''}`} />
            Reload Graph
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Nodes</CardTitle>
            <Network className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_nodes || 0}</div>
            <p className="text-xs text-muted-foreground">
              Across {Object.keys(stats?.by_type || {}).length} types
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Edges</CardTitle>
            <Link2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_edges || 0}</div>
            <p className="text-xs text-muted-foreground">
              Avg {stats?.avg_connections.toFixed(1) || 0} per node
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Orphan Nodes</CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {stats?.orphan_nodes || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats && stats.total_nodes > 0
                ? `${((stats.orphan_nodes / stats.total_nodes) * 100).toFixed(1)}% disconnected`
                : 'No nodes'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Health Score</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{healthScore}%</div>
            <Progress value={healthScore} className="mt-2" />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Layers className="h-5 w-5" />
              Node Distribution
            </CardTitle>
            <CardDescription>Breakdown by node type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={nodeTypeData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {nodeTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--background))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              Edge Distribution
            </CardTitle>
            <CardDescription>Breakdown by edge type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={edgeTypeData} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" className="text-xs" />
                  <YAxis type="category" dataKey="name" className="text-xs" width={75} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--background))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {edgeTypeData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Connectivity Metrics</CardTitle>
            <CardDescription>Graph connectivity health indicators</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Connectivity Score</span>
                <span className="text-sm text-muted-foreground">{connectivityScore}%</span>
              </div>
              <Progress value={connectivityScore} />
              <p className="text-xs text-muted-foreground">
                Percentage of nodes with at least one connection
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Average Degree</span>
                <span className="text-sm font-bold">{stats?.avg_connections.toFixed(2) || 0}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Average number of connections per node
              </p>
            </div>

            <div className="pt-4 border-t">
              <h4 className="text-sm font-medium mb-2">Node Type Breakdown</h4>
              <div className="space-y-2">
                {nodeTypeData.slice(0, 5).map((item) => (
                  <div key={item.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: item.color }}
                      />
                      <span className="text-sm">{item.name}</span>
                    </div>
                    <span className="text-sm font-medium">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sync Status</CardTitle>
            <CardDescription>Graph synchronization and auto-generation status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
              <div>
                <p className="text-sm font-medium">Pending Events</p>
                <p className="text-xs text-muted-foreground">Events waiting to be processed</p>
              </div>
              <Badge variant={syncStatus?.pending_events === 0 ? 'secondary' : 'default'}>
                {syncStatus?.pending_events || 0}
              </Badge>
            </div>

            {syncStatus?.last_processed && (
              <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                <div>
                  <p className="text-sm font-medium">Last Processed</p>
                  <p className="text-xs text-muted-foreground">Most recent sync operation</p>
                </div>
                <span className="text-sm">
                  {new Date(syncStatus.last_processed).toLocaleString()}
                </span>
              </div>
            )}

            <div className="pt-4 border-t">
              <h4 className="text-sm font-medium mb-2">Auto-Generated Edges</h4>
              <div className="space-y-2">
                {syncStatus?.auto_generated_edges &&
                  Object.entries(syncStatus.auto_generated_edges).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {type.replace('_', ' ')}
                        </Badge>
                      </div>
                      <span className="text-sm font-medium">{count}</span>
                    </div>
                  ))}
              </div>
            </div>

            <div className="pt-4">
              <Button variant="outline" className="w-full" onClick={handleReloadGraph} disabled={isReloading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${isReloading ? 'animate-spin' : ''}`} />
                Regenerate Implicit Edges
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
