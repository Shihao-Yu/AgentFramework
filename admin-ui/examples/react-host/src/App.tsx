import { useEffect, useRef } from 'react'
import '@common/context-management-widget'

interface AdminUIWidgetElement extends HTMLElement {
  navigate(path: string): void
  refresh(): void
  setTheme(theme: 'light' | 'dark' | 'system'): void
}

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace JSX {
    interface IntrinsicElements {
      'context-management-widget': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          'api-base-url'?: string
          'tenant-id'?: string
          'initial-route'?: string
          theme?: string
        },
        HTMLElement
      >
    }
  }
}

function App() {
  const widgetRef = useRef<AdminUIWidgetElement>(null)

  useEffect(() => {
    const widget = widgetRef.current
    if (!widget) return

    const handleReady = () => console.log('Widget ready')
    const handleError = (e: Event) => console.error('Widget error:', (e as CustomEvent).detail)

    widget.addEventListener('ready', handleReady)
    widget.addEventListener('error', handleError)

    return () => {
      widget.removeEventListener('ready', handleReady)
      widget.removeEventListener('error', handleError)
    }
  }, [])

  return (
    <context-management-widget
      ref={widgetRef}
      api-base-url="http://localhost:8000"
      tenant-id="demo-tenant"
      initial-route="/"
      theme="system"
    />
  )
}

export default App
