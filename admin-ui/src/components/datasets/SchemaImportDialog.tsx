import { useState, useCallback } from 'react'
import { Upload, Database, Search, Globe, Server } from 'lucide-react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'

import {
  type SourceType,
  type DatasetOnboardRequest,
  type DatasetOnboardResponse,
  SOURCE_TYPE_LABELS,
  SOURCE_TYPE_PLACEHOLDERS,
} from '@/types/queryforge'

const SOURCE_TYPE_ICONS: Record<SourceType, React.ReactNode> = {
  postgres: <Database className="h-5 w-5" />,
  opensearch: <Search className="h-5 w-5" />,
  rest_api: <Globe className="h-5 w-5" />,
  clickhouse: <Server className="h-5 w-5" />,
}

interface SchemaImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onImport: (request: DatasetOnboardRequest) => Promise<DatasetOnboardResponse>
  tenantId: string
  availableSources?: SourceType[]
}

export function SchemaImportDialog({
  open,
  onOpenChange,
  onImport,
  tenantId,
  availableSources = ['postgres', 'opensearch', 'rest_api', 'clickhouse'],
}: SchemaImportDialogProps) {
  const [sourceType, setSourceType] = useState<SourceType>('postgres')
  const [datasetName, setDatasetName] = useState('')
  const [rawSchema, setRawSchema] = useState('')
  const [description, setDescription] = useState('')
  const [enableEnrichment, setEnableEnrichment] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSourceTypeChange = useCallback((type: SourceType) => {
    setSourceType(type)
    setRawSchema('')
    setError(null)
  }, [])

  const handleSubmit = async () => {
    setError(null)

    if (!datasetName.trim()) {
      setError('Dataset name is required')
      return
    }

    if (!rawSchema.trim()) {
      setError('Schema definition is required')
      return
    }

    if (!/^[a-z][a-z0-9_]*$/.test(datasetName)) {
      setError('Dataset name must start with a letter and contain only lowercase letters, numbers, and underscores')
      return
    }

    setIsSubmitting(true)
    try {
      const result = await onImport({
        tenant_id: tenantId,
        dataset_name: datasetName.trim(),
        source_type: sourceType,
        raw_schema: rawSchema,
        description: description.trim() || undefined,
        enable_enrichment: enableEnrichment,
      })

      if (result.status === 'error') {
        setError(result.error || 'Failed to import schema')
        return
      }

      setDatasetName('')
      setRawSchema('')
      setDescription('')
      setEnableEnrichment(false)
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!isSubmitting) {
      setError(null)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Import Schema
          </DialogTitle>
          <DialogDescription>
            Import a schema definition to create a new dataset for query generation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="space-y-3">
            <Label>Source Type</Label>
            <div className="grid grid-cols-4 gap-2">
              {availableSources.map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleSourceTypeChange(type)}
                  className={cn(
                    'flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all',
                    sourceType === type
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:border-primary/50'
                  )}
                >
                  {SOURCE_TYPE_ICONS[type]}
                  <span className="text-xs font-medium">{SOURCE_TYPE_LABELS[type]}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="dataset-name">Dataset Name</Label>
            <Input
              id="dataset-name"
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value.toLowerCase())}
              placeholder="e.g., orders, products, users"
            />
            <p className="text-xs text-muted-foreground">
              Lowercase letters, numbers, and underscores only. This will be used as the table/index name.
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="raw-schema">Schema Definition</Label>
            <Textarea
              id="raw-schema"
              value={rawSchema}
              onChange={(e) => setRawSchema(e.target.value)}
              placeholder={SOURCE_TYPE_PLACEHOLDERS[sourceType]}
              rows={12}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              {sourceType === 'postgres' && 'Paste your CREATE TABLE DDL statement'}
              {sourceType === 'opensearch' && 'Paste your index mapping JSON'}
              {sourceType === 'rest_api' && 'Paste your OpenAPI/Swagger specification (YAML or JSON)'}
              {sourceType === 'clickhouse' && 'Paste your ClickHouse CREATE TABLE statement'}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description (optional)</Label>
            <Input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this dataset..."
            />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="enable-enrichment"
              checked={enableEnrichment}
              onCheckedChange={(checked) => setEnableEnrichment(!!checked)}
            />
            <Label htmlFor="enable-enrichment" className="text-sm font-normal cursor-pointer">
              Enable AI enrichment (automatically generate field descriptions)
            </Label>
          </div>

          {error && (
            <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? 'Importing...' : 'Import Schema'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
