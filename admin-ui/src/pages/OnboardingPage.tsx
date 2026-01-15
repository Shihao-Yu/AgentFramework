import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus, X, Upload, Loader2, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useTenantContext } from '@/components/tenant/TenantProvider'
import { useOnboarding } from '@/hooks/useOnboarding'

const NODE_TYPES = [
  { value: 'FAQ', label: 'FAQ' },
  { value: 'PLAYBOOK', label: 'Playbook' },
  { value: 'CONCEPT', label: 'Concept' },
  { value: 'FEATURE_PERMISSION', label: 'Feature Permission' },
  { value: 'ENTITY', label: 'Entity' },
] as const

interface ContentBox {
  id: string
  text: string
  nodeTypes: string[]
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 9)
}

export function OnboardingPage() {
  const { currentTenantId } = useTenantContext()
  const { onboard, isLoading, error } = useOnboarding()

  const [sourceTag, setSourceTag] = useState('')
  const [contentBoxes, setContentBoxes] = useState<ContentBox[]>([
    { id: generateId(), text: '', nodeTypes: ['FAQ'] },
  ])
  const [result, setResult] = useState<{ created: number; stagingIds: number[] } | null>(null)

  const handleAddBox = useCallback(() => {
    setContentBoxes((prev) => [
      ...prev,
      { id: generateId(), text: '', nodeTypes: ['FAQ'] },
    ])
  }, [])

  const handleRemoveBox = useCallback((id: string) => {
    setContentBoxes((prev) => prev.filter((box) => box.id !== id))
  }, [])

  const handleTextChange = useCallback((id: string, text: string) => {
    setContentBoxes((prev) =>
      prev.map((box) => (box.id === id ? { ...box, text } : box))
    )
  }, [])

  const handleNodeTypeToggle = useCallback((id: string, nodeType: string) => {
    setContentBoxes((prev) =>
      prev.map((box) => {
        if (box.id !== id) return box
        const hasType = box.nodeTypes.includes(nodeType)
        return {
          ...box,
          nodeTypes: hasType
            ? box.nodeTypes.filter((t) => t !== nodeType)
            : [...box.nodeTypes, nodeType],
        }
      })
    )
  }, [])

  const handleSubmit = useCallback(async () => {
    const validBoxes = contentBoxes.filter(
      (box) => box.text.trim().length > 0 && box.nodeTypes.length > 0
    )

    if (validBoxes.length === 0) {
      return
    }

    try {
      const response = await onboard({
        items: validBoxes.map((box) => ({
          text: box.text,
          node_types: box.nodeTypes,
        })),
        tenant_id: currentTenantId || 'default',
        source_tag: sourceTag,
      })

      setResult({
        created: response.created,
        stagingIds: response.staging_ids,
      })

      setContentBoxes([{ id: generateId(), text: '', nodeTypes: ['FAQ'] }])
      setSourceTag('')
    } catch {
    }
  }, [contentBoxes, sourceTag, currentTenantId, onboard])

  const isValid = contentBoxes.some(
    (box) => box.text.trim().length > 0 && box.nodeTypes.length > 0
  )

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Context Onboarding</h1>
          <p className="text-muted-foreground">
            Paste raw text content to extract structured knowledge nodes.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Source tag (optional)"
            value={sourceTag}
            onChange={(e) => setSourceTag(e.target.value)}
            className="w-48"
          />
          <Button onClick={handleSubmit} disabled={!isValid || isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Extracting...
              </>
            ) : (
              <>
                <Upload className="mr-2 h-4 w-4" />
                Extract & Stage
              </>
            )}
          </Button>
        </div>
      </div>

      {result && (
        <Card className="border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-600" />
              <div>
                <p className="font-medium text-green-800 dark:text-green-200">
                  Created {result.created} staging node{result.created !== 1 ? 's' : ''}
                </p>
                <p className="text-sm text-green-700 dark:text-green-300">
                  <Link to="/staging" className="underline hover:no-underline">
                    Go to Staging Queue
                  </Link>{' '}
                  to review and approve.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
          <CardContent className="pt-6">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Content to Extract</CardTitle>
            <CardDescription>
              Add content boxes and select which node types to extract. All items go to staging for review.
            </CardDescription>
          </div>
          <Button variant="outline" onClick={handleAddBox}>
            <Plus className="mr-2 h-4 w-4" />
            Add Content
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {contentBoxes.map((box, index) => (
            <div key={box.id} className="border rounded-lg p-4 space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-base font-medium">Content {index + 1}</Label>
                {contentBoxes.length > 1 && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleRemoveBox(box.id)}
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <Textarea
                placeholder="Paste your content here..."
                value={box.text}
                onChange={(e) => handleTextChange(box.id, e.target.value)}
                className="min-h-[150px] font-mono text-sm"
              />
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">Extract as</Label>
                <div className="flex flex-wrap gap-2">
                  {NODE_TYPES.map((nodeType) => {
                    const isSelected = box.nodeTypes.includes(nodeType.value)
                    return (
                      <Badge
                        key={nodeType.value}
                        variant={isSelected ? 'default' : 'outline'}
                        className={cn(
                          'cursor-pointer select-none transition-colors',
                          isSelected 
                            ? 'hover:bg-primary/80' 
                            : 'hover:bg-accent hover:text-accent-foreground'
                        )}
                        onClick={() => handleNodeTypeToggle(box.id, nodeType.value)}
                      >
                        {nodeType.label}
                      </Badge>
                    )
                  })}
                </div>
                {box.nodeTypes.length === 0 && (
                  <p className="text-sm text-destructive">
                    Select at least one node type
                  </p>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
