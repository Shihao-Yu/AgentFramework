import { useState, useCallback, useEffect } from 'react'
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'
import { MonacoEditor } from '@/components/editors'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { validateYAMLSchema, errorsToMonacoMarkers, type ValidationError } from '@/lib/schemas/yamlSchemaV1'
import type { editor } from 'monaco-editor'

interface SchemaEditorProps {
  value: string
  onChange: (value: string) => void
  onSave?: () => void
  isSaving?: boolean
  readOnly?: boolean
}

export function SchemaEditor({
  value,
  onChange,
  onSave,
  isSaving = false,
  readOnly = false,
}: SchemaEditorProps) {
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([])
  const [markers, setMarkers] = useState<editor.IMarkerData[]>([])
  const [isValidating, setIsValidating] = useState(false)

  useEffect(() => {
    if (!value) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setValidationErrors([])
      setMarkers([])
      return
    }

    setIsValidating(true)
    const timeout = setTimeout(() => {
      const result = validateYAMLSchema(value)
      setValidationErrors(result.errors)
      setMarkers(errorsToMonacoMarkers(result.errors))
      setIsValidating(false)
    }, 500)

    return () => clearTimeout(timeout)
  }, [value])

  const handleChange = useCallback(
    (newValue: string) => {
      onChange(newValue)
    },
    [onChange]
  )

  const isValid = validationErrors.length === 0 && value.trim().length > 0

  return (
    <div className="space-y-3">
      {/* Validation Status Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isValidating ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Validating...</span>
            </>
          ) : isValid ? (
            <>
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <span className="text-sm text-green-600">Schema is valid</span>
            </>
          ) : validationErrors.length > 0 ? (
            <>
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-sm text-destructive">
                {validationErrors.length} validation error{validationErrors.length > 1 ? 's' : ''}
              </span>
            </>
          ) : (
            <span className="text-sm text-muted-foreground">Enter schema definition</span>
          )}
        </div>

        {onSave && !readOnly && (
          <Button onClick={onSave} disabled={!isValid || isSaving} size="sm">
            {isSaving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Changes'
            )}
          </Button>
        )}
      </div>

      {/* Monaco Editor */}
      <MonacoEditor
        value={value}
        onChange={handleChange}
        language="yaml"
        height={500}
        readOnly={readOnly}
        markers={markers}
      />

      {/* Error Details */}
      {validationErrors.length > 0 && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3">
          <h4 className="font-medium text-destructive mb-2">Validation Errors:</h4>
          <ul className="space-y-1">
            {validationErrors.map((error, index) => (
              <li key={index} className="text-sm flex items-start gap-2">
                <Badge variant="destructive" className="text-xs shrink-0">
                  {error.line ? `Line ${error.line}` : 'Error'}
                </Badge>
                <span className="text-destructive">
                  {error.path && <span className="font-mono">{error.path}: </span>}
                  {error.message}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
