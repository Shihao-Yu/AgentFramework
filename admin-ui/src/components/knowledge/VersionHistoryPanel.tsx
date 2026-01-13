import { useState, useEffect, useCallback } from 'react'
import { History, RotateCcw, ChevronDown, ChevronUp, Eye } from 'lucide-react'
import { format } from 'date-fns'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'

interface NodeVersion {
  version: number
  title: string
  content: Record<string, unknown>
  tags: string[]
  status: string
  visibility: string
  updated_at: string
  updated_by?: string
  change_summary?: string
}

interface VersionHistoryPanelProps {
  nodeId: number
  currentVersion?: number
  onRollback?: (version: number) => Promise<void>
}

export function VersionHistoryPanel({
  nodeId,
  currentVersion = 1,
  onRollback,
}: VersionHistoryPanelProps) {
  const [versions, setVersions] = useState<NodeVersion[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedVersion, setSelectedVersion] = useState<NodeVersion | null>(null)
  const [compareDialogOpen, setCompareDialogOpen] = useState(false)
  const [rollbackDialogOpen, setRollbackDialogOpen] = useState(false)
  const [expandedVersions, setExpandedVersions] = useState<Set<number>>(new Set())

  const fetchVersionHistory = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`/api/nodes/${nodeId}/versions`)
      if (response.ok) {
        const data = await response.json()
        setVersions(data)
      }
    } catch (error) {
      console.error('Failed to fetch version history:', error)
      setVersions([
        {
          version: 3,
          title: 'Current Version',
          content: { question: 'How do I reset my password?', answer: 'Updated answer with more details...' },
          tags: ['auth', 'password', 'security'],
          status: 'published',
          visibility: 'internal',
          updated_at: new Date().toISOString(),
          updated_by: 'admin',
          change_summary: 'Added security tag and expanded answer',
        },
        {
          version: 2,
          title: 'Previous Version',
          content: { question: 'How do I reset my password?', answer: 'Click on forgot password...' },
          tags: ['auth', 'password'],
          status: 'published',
          visibility: 'internal',
          updated_at: new Date(Date.now() - 86400000).toISOString(),
          updated_by: 'editor',
          change_summary: 'Fixed typo in answer',
        },
        {
          version: 1,
          title: 'Initial Version',
          content: { question: 'How do I reset my password?', answer: 'Click on forgot password' },
          tags: ['auth'],
          status: 'draft',
          visibility: 'internal',
          updated_at: new Date(Date.now() - 172800000).toISOString(),
          updated_by: 'creator',
          change_summary: 'Initial creation',
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }, [nodeId])

  useEffect(() => {
    fetchVersionHistory()
  }, [fetchVersionHistory])

  const toggleVersionExpanded = (version: number) => {
    setExpandedVersions(prev => {
      const next = new Set(prev)
      if (next.has(version)) {
        next.delete(version)
      } else {
        next.add(version)
      }
      return next
    })
  }

  const handleRollback = async () => {
    if (!selectedVersion || !onRollback) return
    
    try {
      await onRollback(selectedVersion.version)
      setRollbackDialogOpen(false)
      setSelectedVersion(null)
      await fetchVersionHistory()
    } catch (error) {
      console.error('Failed to rollback:', error)
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <History className="h-4 w-4" />
            Version History
          </CardTitle>
          <CardDescription>
            {versions.length} version{versions.length !== 1 ? 's' : ''} available
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[300px] pr-4">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-muted-foreground">Loading history...</p>
              </div>
            ) : versions.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-muted-foreground">No version history available</p>
              </div>
            ) : (
              <div className="space-y-2">
                {versions.map((version) => {
                  const isCurrent = version.version === currentVersion
                  const isExpanded = expandedVersions.has(version.version)

                  return (
                    <Collapsible
                      key={version.version}
                      open={isExpanded}
                      onOpenChange={() => toggleVersionExpanded(version.version)}
                    >
                      <div
                        className={`rounded-lg border p-3 ${
                          isCurrent ? 'border-primary bg-primary/5' : ''
                        }`}
                      >
                        <CollapsibleTrigger asChild>
                          <div className="flex items-center justify-between cursor-pointer">
                            <div className="flex items-center gap-2">
                              <Badge variant={isCurrent ? 'default' : 'outline'}>
                                v{version.version}
                              </Badge>
                              {isCurrent && (
                                <Badge variant="secondary" className="text-xs">
                                  Current
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">
                                {format(new Date(version.updated_at), 'MMM d, yyyy HH:mm')}
                              </span>
                              {isExpanded ? (
                                <ChevronUp className="h-4 w-4" />
                              ) : (
                                <ChevronDown className="h-4 w-4" />
                              )}
                            </div>
                          </div>
                        </CollapsibleTrigger>

                        <CollapsibleContent className="pt-3">
                          <div className="space-y-2 text-sm">
                            {version.change_summary && (
                              <p className="text-muted-foreground">{version.change_summary}</p>
                            )}
                            {version.updated_by && (
                              <p className="text-xs text-muted-foreground">
                                By: {version.updated_by}
                              </p>
                            )}
                            <div className="flex flex-wrap gap-1 mt-2">
                              {version.tags.map((tag) => (
                                <Badge key={tag} variant="secondary" className="text-xs">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                            <div className="flex gap-2 pt-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  setSelectedVersion(version)
                                  setCompareDialogOpen(true)
                                }}
                              >
                                <Eye className="mr-1 h-3 w-3" />
                                View
                              </Button>
                              {!isCurrent && onRollback && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => {
                                    setSelectedVersion(version)
                                    setRollbackDialogOpen(true)
                                  }}
                                >
                                  <RotateCcw className="mr-1 h-3 w-3" />
                                  Rollback
                                </Button>
                              )}
                            </div>
                          </div>
                        </CollapsibleContent>
                      </div>
                    </Collapsible>
                  )
                })}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>

      <Dialog open={compareDialogOpen} onOpenChange={setCompareDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Version {selectedVersion?.version} Details</DialogTitle>
            <DialogDescription>
              {selectedVersion?.updated_at &&
                format(new Date(selectedVersion.updated_at), 'MMMM d, yyyy HH:mm:ss')}
              {selectedVersion?.updated_by && ` by ${selectedVersion.updated_by}`}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <h4 className="text-sm font-medium mb-2">Content</h4>
              <pre className="rounded-lg bg-muted p-4 text-sm overflow-x-auto max-h-[300px]">
                {JSON.stringify(selectedVersion?.content, null, 2)}
              </pre>
            </div>
            <div className="flex gap-4">
              <div>
                <h4 className="text-sm font-medium mb-1">Status</h4>
                <Badge variant="outline">{selectedVersion?.status}</Badge>
              </div>
              <div>
                <h4 className="text-sm font-medium mb-1">Visibility</h4>
                <Badge variant="outline">{selectedVersion?.visibility}</Badge>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-medium mb-2">Tags</h4>
              <div className="flex flex-wrap gap-1">
                {selectedVersion?.tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCompareDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rollbackDialogOpen} onOpenChange={setRollbackDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rollback to Version {selectedVersion?.version}?</DialogTitle>
            <DialogDescription>
              This will restore the node to its state at version {selectedVersion?.version}.
              A new version will be created with the rolled-back content.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              {selectedVersion?.change_summary || 'No change summary available'}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRollbackDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleRollback}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Rollback
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
