import { useState } from 'react'
import { ArrowLeftRight } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'

import {
  EdgeType,
  EdgeTypeLabels,
  NodeTypeConfig,
  type CreateEdgeRequest,
  type GraphNode,
} from '@/types/graph'

const MANUAL_EDGE_TYPES = [
  EdgeType.RELATED,
  EdgeType.PARENT,
  EdgeType.EXAMPLE_OF,
] as const

interface AddEdgeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: CreateEdgeRequest) => Promise<void>
  sourceNode: GraphNode | null
  targetNode: GraphNode | null
}

export function AddEdgeDialog({
  open,
  onOpenChange,
  onSubmit,
  sourceNode,
  targetNode,
}: AddEdgeDialogProps) {
  const [edgeType, setEdgeType] = useState<EdgeType>(EdgeType.RELATED)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSwapped, setIsSwapped] = useState(false)

  if (!sourceNode || !targetNode) return null

  const displaySource = isSwapped ? targetNode : sourceNode
  const displayTarget = isSwapped ? sourceNode : targetNode

  const handleSubmit = async () => {
    setIsSubmitting(true)
    try {
      await onSubmit({
        source_id: displaySource.id,
        target_id: displayTarget.id,
        edge_type: edgeType,
        weight: 1.0,
      })
      setEdgeType(EdgeType.RELATED)
      setIsSwapped(false)
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  const sourceConfig = NodeTypeConfig[displaySource.node_type]
  const targetConfig = NodeTypeConfig[displayTarget.node_type]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Create Edge</DialogTitle>
          <DialogDescription>
            Connect two nodes with a relationship
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="flex items-center justify-center gap-4">
            <div className="flex flex-col items-center gap-2 p-3 border rounded-lg bg-muted/50 flex-1">
              <span className="text-2xl">{sourceConfig.icon}</span>
              <span className="text-sm font-medium text-center line-clamp-2">
                {displaySource.title}
              </span>
              <Badge variant="outline" className="text-xs">Source</Badge>
            </div>
            
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setIsSwapped(!isSwapped)}
              title="Swap source and target"
              className="shrink-0"
            >
              <ArrowLeftRight className="h-5 w-5" />
            </Button>
            
            <div className="flex flex-col items-center gap-2 p-3 border rounded-lg bg-muted/50 flex-1">
              <span className="text-2xl">{targetConfig.icon}</span>
              <span className="text-sm font-medium text-center line-clamp-2">
                {displayTarget.title}
              </span>
              <Badge variant="outline" className="text-xs">Target</Badge>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Edge Type</Label>
            <Select
              value={edgeType}
              onValueChange={(v) => setEdgeType(v as EdgeType)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MANUAL_EDGE_TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {EdgeTypeLabels[type]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {edgeType === EdgeType.RELATED && 'General relationship between nodes'}
              {edgeType === EdgeType.PARENT && 'Source is a parent/container of target'}
              {edgeType === EdgeType.EXAMPLE_OF && 'Target is an example of source (e.g., example of a schema)'}
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Edge'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
