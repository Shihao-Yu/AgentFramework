import { useState, useCallback } from 'react'
import { Sparkles, Copy, Save, Check, AlertCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { useQueryGeneration } from '@/hooks/useQueryForge'
import { QUERY_TYPE_LABELS, type QueryType } from '@/types/queryforge'

interface QueryGeneratorPanelProps {
  datasetName: string
  tenantId: string
  onSaveAsExample?: (question: string, query: string, queryType: QueryType, explanation?: string) => void
  className?: string
}

export function QueryGeneratorPanel({
  datasetName,
  tenantId,
  onSaveAsExample,
  className,
}: QueryGeneratorPanelProps) {
  const [question, setQuestion] = useState('')
  const [copied, setCopied] = useState(false)
  const { generateQuery, isGenerating, lastResult } = useQueryGeneration()

  const handleGenerate = useCallback(async () => {
    if (!question.trim()) return

    await generateQuery({
      tenant_id: tenantId,
      dataset_name: datasetName,
      question: question.trim(),
      include_explanation: true,
    })
  }, [question, tenantId, datasetName, generateQuery])

  const handleCopy = useCallback(async () => {
    if (lastResult?.query) {
      await navigator.clipboard.writeText(lastResult.query)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [lastResult])

  const handleSaveAsExample = useCallback(() => {
    if (lastResult?.query && lastResult.query_type && onSaveAsExample) {
      onSaveAsExample(
        question,
        lastResult.query,
        lastResult.query_type,
        lastResult.explanation
      )
    }
  }, [question, lastResult, onSaveAsExample])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleGenerate()
    }
  }, [handleGenerate])

  const confidenceColor = lastResult?.confidence
    ? lastResult.confidence >= 0.8
      ? 'text-green-600'
      : lastResult.confidence >= 0.6
        ? 'text-yellow-600'
        : 'text-red-600'
    : ''

  return (
    <Card className={cn('', className)}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Query Generator
        </CardTitle>
        <CardDescription>
          Generate queries from natural language for <strong>{datasetName}</strong>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="question">Ask a question</Label>
          <Textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g., Show all pending orders from last week"
            rows={3}
            className="resize-none"
          />
          <p className="text-xs text-muted-foreground">
            Press Ctrl+Enter to generate
          </p>
        </div>

        <Button
          onClick={handleGenerate}
          disabled={isGenerating || !question.trim()}
          className="w-full"
        >
          {isGenerating ? (
            <>
              <Sparkles className="mr-2 h-4 w-4 animate-pulse" />
              Generating...
            </>
          ) : (
            <>
              <Sparkles className="mr-2 h-4 w-4" />
              Generate Query
            </>
          )}
        </Button>

        {lastResult && (
          <div className="space-y-3 pt-2">
            {lastResult.status === 'error' ? (
              <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm flex items-start gap-2">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <span>{lastResult.error}</span>
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Label>Generated Query</Label>
                    {lastResult.query_type && (
                      <Badge variant="outline" className="text-xs">
                        {QUERY_TYPE_LABELS[lastResult.query_type]}
                      </Badge>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCopy}
                      className="h-7 px-2"
                    >
                      {copied ? (
                        <Check className="h-3.5 w-3.5 text-green-600" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    {onSaveAsExample && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleSaveAsExample}
                        className="h-7 px-2"
                        title="Save as training example"
                      >
                        <Save className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                </div>

                <pre className="p-3 rounded-md bg-muted text-sm font-mono overflow-x-auto whitespace-pre-wrap">
                  {lastResult.query}
                </pre>

                {lastResult.explanation && (
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground">Explanation</Label>
                    <p className="text-sm text-muted-foreground">
                      {lastResult.explanation}
                    </p>
                  </div>
                )}

                {lastResult.confidence !== undefined && (
                  <div className="flex items-center gap-2">
                    <Label className="text-xs text-muted-foreground">Confidence</Label>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            lastResult.confidence >= 0.8
                              ? 'bg-green-500'
                              : lastResult.confidence >= 0.6
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                          )}
                          style={{ width: `${lastResult.confidence * 100}%` }}
                        />
                      </div>
                      <span className={cn('text-xs font-medium', confidenceColor)}>
                        {Math.round(lastResult.confidence * 100)}%
                      </span>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
