import { useCallback } from 'react'
import MDEditor from '@uiw/react-md-editor'
import { cn } from '@/lib/utils'

interface MarkdownEditorProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  height?: number
  preview?: 'edit' | 'live' | 'preview'
  className?: string
  disabled?: boolean
}

export function MarkdownEditor({
  value,
  onChange,
  placeholder = 'Write your content here...',
  height = 300,
  preview = 'live',
  className,
  disabled = false,
}: MarkdownEditorProps) {
  const handleChange = useCallback(
    (val?: string) => {
      onChange(val || '')
    },
    [onChange]
  )

  return (
    <div className={cn('markdown-editor', className)} data-color-mode="light">
      <MDEditor
        value={value}
        onChange={handleChange}
        preview={preview}
        height={height}
        textareaProps={{
          placeholder,
          disabled,
        }}
        hideToolbar={disabled}
      />
    </div>
  )
}

// Read-only markdown preview component
interface MarkdownPreviewProps {
  content: string
  className?: string
}

export function MarkdownPreview({ content, className }: MarkdownPreviewProps) {
  return (
    <div className={cn('markdown-preview', className)} data-color-mode="light">
      <MDEditor.Markdown source={content} />
    </div>
  )
}
