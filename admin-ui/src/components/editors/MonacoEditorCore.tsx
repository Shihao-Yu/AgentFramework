import { useCallback, useRef, useEffect } from 'react'
import Editor, { type OnMount, type OnChange } from '@monaco-editor/react'
import type { editor } from 'monaco-editor'
import { cn } from '@/lib/utils'

export type MonacoLanguage = 'yaml' | 'json' | 'text' | 'markdown'

export interface MonacoEditorProps {
  value: string
  onChange: (value: string) => void
  language?: MonacoLanguage
  height?: number | string
  className?: string
  readOnly?: boolean
  placeholder?: string
  markers?: editor.IMarkerData[]
  onValidate?: (markers: editor.IMarkerData[]) => void
}

export function MonacoEditorCore({
  value,
  onChange,
  language = 'yaml',
  height = 400,
  className,
  readOnly = false,
  markers = [],
  onValidate,
}: MonacoEditorProps) {
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null)
  const monacoRef = useRef<typeof import('monaco-editor') | null>(null)

  const handleEditorDidMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor
    monacoRef.current = monaco

    editor.updateOptions({
      minimap: { enabled: false },
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      tabSize: 2,
      insertSpaces: true,
      automaticLayout: true,
      fontSize: 13,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
    })
  }, [])

  const handleChange: OnChange = useCallback(
    (val) => {
      onChange(val || '')
    },
    [onChange]
  )

  useEffect(() => {
    if (editorRef.current && monacoRef.current && markers.length >= 0) {
      const model = editorRef.current.getModel()
      if (model) {
        monacoRef.current.editor.setModelMarkers(model, 'validation', markers)
      }
    }
  }, [markers])

  useEffect(() => {
    if (onValidate && editorRef.current && monacoRef.current) {
      const model = editorRef.current.getModel()
      if (model) {
        const currentMarkers = monacoRef.current.editor.getModelMarkers({ resource: model.uri })
        onValidate(currentMarkers)
      }
    }
  }, [value, onValidate])

  return (
    <div className={cn('monaco-editor-wrapper border rounded-md overflow-hidden', className)}>
      <Editor
        height={height}
        language={language === 'text' ? 'plaintext' : language}
        value={value}
        onChange={handleChange}
        onMount={handleEditorDidMount}
        theme="vs-light"
        options={{
          readOnly,
          domReadOnly: readOnly,
        }}
        loading={
          <div className="flex items-center justify-center h-full text-muted-foreground">
            Loading editor...
          </div>
        }
      />
    </div>
  )
}

export interface JSONEditorProps {
  value: string
  onChange: (value: string) => void
  height?: number | string
  className?: string
  readOnly?: boolean
  onValidationChange?: (isValid: boolean, error?: string) => void
}

export function JSONEditorCore({
  value,
  onChange,
  height = 300,
  className,
  readOnly = false,
  onValidationChange,
}: JSONEditorProps) {
  const handleChange = useCallback(
    (val: string) => {
      onChange(val)

      if (onValidationChange) {
        try {
          if (val.trim()) {
            JSON.parse(val)
          }
          onValidationChange(true)
        } catch (error) {
          onValidationChange(false, (error as Error).message)
        }
      }
    },
    [onChange, onValidationChange]
  )

  return (
    <MonacoEditorCore
      value={value}
      onChange={handleChange}
      language="json"
      height={height}
      className={className}
      readOnly={readOnly}
    />
  )
}
