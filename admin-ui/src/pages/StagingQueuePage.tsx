import { useState, useCallback } from 'react'
import { CheckCircle, XCircle, Pencil, ArrowRight, GitMerge, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useStaging } from '@/hooks/useStaging'
import { 
  StagingContentPreview, 
  StagingEditForm, 
  getNodeTypeLabel, 
  getNodeTypeBadgeColor,
  type StagingEditData
} from '@/components/staging'
import type { StagingKnowledgeItem } from '@/types/knowledge'
import { format } from 'date-fns'

export function StagingQueuePage() {
  const {
    pendingItems,
    countByAction,
    getMergeTarget,
    approveItem,
    rejectItem,
    editAndApprove,
  } = useStaging()

  const [selectedItem, setSelectedItem] = useState<StagingKnowledgeItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [editedData, setEditedData] = useState<StagingEditData>({
    title: '',
    content: {},
    tags: [],
  })
  const [mergeTarget, setMergeTarget] = useState<{ id: number; title: string; content: Record<string, unknown> } | null>(null)

  const handleOpenReview = useCallback(async (item: StagingKnowledgeItem) => {
    setSelectedItem(item)
    setEditedData({
      title: item.title,
      content: { ...item.content },
      tags: [...item.tags],
    })
    setRejectReason('')
    
    // Fetch merge target if applicable
    if (item.merge_with_id) {
      const target = await getMergeTarget(item)
      if (target) {
        setMergeTarget({
          id: target.id,
          title: target.title,
          content: target.content,
        })
      } else {
        setMergeTarget(null)
      }
    } else {
      setMergeTarget(null)
    }
  }, [getMergeTarget])

  const handleApprove = useCallback(async () => {
    if (!selectedItem) return
    await editAndApprove(selectedItem.id, editedData)
    setSelectedItem(null)
    setMergeTarget(null)
  }, [selectedItem, editedData, editAndApprove])

  const handleReject = useCallback(async () => {
    if (!selectedItem) return
    await rejectItem(selectedItem.id, rejectReason)
    setSelectedItem(null)
    setMergeTarget(null)
  }, [selectedItem, rejectReason, rejectItem])

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'new':
        return <Badge className="bg-blue-500"><Plus className="mr-1 h-3 w-3" />New</Badge>
      case 'merge':
        return <Badge className="bg-purple-500"><GitMerge className="mr-1 h-3 w-3" />Merge</Badge>
      case 'add_variant':
        return <Badge className="bg-green-500"><ArrowRight className="mr-1 h-3 w-3" />Add Variant</Badge>
      default:
        return <Badge variant="secondary">{action}</Badge>
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Staging Queue</h1>
        <p className="text-muted-foreground">
          Review and approve knowledge items generated from support tickets.
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{pendingItems.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">New Items</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{countByAction.new}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Merge Suggestions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{countByAction.merge}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Variant Additions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{countByAction.add_variant}</div>
          </CardContent>
        </Card>
      </div>

      {/* Queue List */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all">All ({pendingItems.length})</TabsTrigger>
          <TabsTrigger value="new">New ({countByAction.new})</TabsTrigger>
          <TabsTrigger value="merge">Merge ({countByAction.merge})</TabsTrigger>
          <TabsTrigger value="variant">Variants ({countByAction.add_variant})</TabsTrigger>
        </TabsList>

        {['all', 'new', 'merge', 'variant'].map((tabValue) => (
          <TabsContent key={tabValue} value={tabValue}>
            <Card>
              <CardHeader>
                <CardTitle>Pending Items</CardTitle>
                <CardDescription>
                  {tabValue === 'all'
                    ? 'All items awaiting review'
                    : tabValue === 'new'
                    ? 'New entries from tickets'
                    : tabValue === 'merge'
                    ? 'Updates to merge with existing items'
                    : 'New variants to add'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {pendingItems
                    .filter((item) => {
                      if (tabValue === 'all') return true
                      if (tabValue === 'new') return item.action === 'new'
                      if (tabValue === 'merge') return item.action === 'merge'
                      if (tabValue === 'variant') return item.action === 'add_variant'
                      return true
                    })
                    .map((item) => {
                      return (
                        <div
                          key={item.id}
                          className="flex items-start justify-between p-4 border rounded-lg hover:bg-accent/50 transition-colors"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              {/* Node Type Badge */}
                              <Badge className={getNodeTypeBadgeColor(item.node_type)}>
                                {getNodeTypeLabel(item.node_type)}
                              </Badge>
                              {getActionBadge(item.action)}
                              {item.similarity !== undefined && item.similarity !== null && (
                                <Badge variant="outline">
                                  {Math.round(item.similarity * 100)}% match
                                </Badge>
                              )}
                              {item.confidence !== undefined && item.confidence !== null && (
                                <Badge variant="secondary">
                                  {Math.round(item.confidence * 100)}% confidence
                                </Badge>
                              )}
                            </div>
                            <h4 className="font-medium truncate">{item.title}</h4>
                            <div className="mt-1">
                              <StagingContentPreview item={item} />
                            </div>
                            {item.merge_with_id && (
                              <div className="mt-2 text-sm">
                                <span className="text-muted-foreground">Merge with ID: </span>
                                <span className="font-medium">#{item.merge_with_id}</span>
                              </div>
                            )}
                            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                              {item.source_reference && (
                                <span>Source: {item.source_reference}</span>
                              )}
                              {item.source && (
                                <span>Via: {item.source}</span>
                              )}
                              <span>{format(new Date(item.created_at), 'MMM d, yyyy HH:mm')}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 ml-4">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenReview(item)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-green-600 hover:text-green-700 hover:bg-green-50"
                              onClick={async () => {
                                await approveItem(item.id)
                              }}
                            >
                              <CheckCircle className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-red-600 hover:text-red-700 hover:bg-red-50"
                              onClick={() => handleOpenReview(item)}
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      )
                    })}
                  {pendingItems.filter((item) => {
                    if (tabValue === 'all') return true
                    if (tabValue === 'new') return item.action === 'new'
                    if (tabValue === 'merge') return item.action === 'merge'
                    if (tabValue === 'variant') return item.action === 'add_variant'
                    return true
                  }).length === 0 && (
                    <div className="text-center py-12 text-muted-foreground">
                      No items pending review
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>

      {/* Review Dialog */}
      <Dialog open={!!selectedItem} onOpenChange={() => { setSelectedItem(null); setMergeTarget(null) }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <div className="flex items-center gap-2">
              {selectedItem && (
                <Badge className={getNodeTypeBadgeColor(selectedItem.node_type)}>
                  {getNodeTypeLabel(selectedItem.node_type)}
                </Badge>
              )}
              <DialogTitle>Review & Edit</DialogTitle>
            </div>
            <DialogDescription>
              {selectedItem?.action === 'new'
                ? `Review and edit this new ${getNodeTypeLabel(selectedItem?.node_type || '')} entry before publishing.`
                : selectedItem?.action === 'merge'
                ? `Review and approve merging this content with an existing ${getNodeTypeLabel(selectedItem?.node_type || '')}.`
                : 'Review this variant before adding.'}
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="flex-1 pr-4">
            {selectedItem && (
              <div className="space-y-6">
                {/* Merge Target Comparison */}
                {selectedItem.action === 'merge' && mergeTarget && (
                  <div className="rounded-lg border p-4 bg-purple-50 dark:bg-purple-950">
                    <h4 className="font-medium mb-2 flex items-center gap-2">
                      <GitMerge className="h-4 w-4" />
                      Existing Item to Merge With
                    </h4>
                    <div className="text-sm">
                      <p className="font-medium">{mergeTarget.title}</p>
                      <p className="text-muted-foreground mt-1">
                        {JSON.stringify(mergeTarget.content).slice(0, 200)}...
                      </p>
                    </div>
                  </div>
                )}

                <Separator />

                {/* Dynamic Edit Form based on node_type */}
                <StagingEditForm
                  item={selectedItem}
                  editedData={editedData}
                  onChange={setEditedData}
                />

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {selectedItem.source_reference && (
                    <div>
                      <span className="text-muted-foreground">Source Reference: </span>
                      <span className="font-medium">{selectedItem.source_reference}</span>
                    </div>
                  )}
                  {selectedItem.source && (
                    <div>
                      <span className="text-muted-foreground">Source: </span>
                      <span className="font-medium">{selectedItem.source}</span>
                    </div>
                  )}
                  <div>
                    <span className="text-muted-foreground">Confidence: </span>
                    <span className="font-medium">
                      {selectedItem.confidence !== undefined && selectedItem.confidence !== null
                        ? `${Math.round(selectedItem.confidence * 100)}%`
                        : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Node Type: </span>
                    <span className="font-medium">{getNodeTypeLabel(selectedItem.node_type)}</span>
                  </div>
                </div>

                {/* Reject Reason */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Rejection Reason (optional)</label>
                  <Textarea
                    placeholder="Provide a reason if rejecting..."
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                  />
                </div>
              </div>
            )}
          </ScrollArea>

          <DialogFooter className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => { setSelectedItem(null); setMergeTarget(null) }}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleReject}>
              <XCircle className="mr-2 h-4 w-4" />
              Reject
            </Button>
            <Button onClick={handleApprove}>
              <CheckCircle className="mr-2 h-4 w-4" />
              Save & Approve
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
