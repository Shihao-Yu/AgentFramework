import type { AdminUIEventPayloads } from '../lib/events'

export interface AdminUIWidgetAttributes {
  'api-base-url'?: string
  'tenant-id'?: string
  'initial-route'?: string
  theme?: 'light' | 'dark' | 'system'
}

export interface AdminUIWidgetElement extends HTMLElement {
  navigate(path: string): void
  refresh(): void
  setTheme(theme: 'light' | 'dark' | 'system'): void
}

export type AdminUIEventMap = {
  [K in keyof AdminUIEventPayloads]: CustomEvent<AdminUIEventPayloads[K]>
}

declare global {
  interface HTMLElementTagNameMap {
    'context-management-widget': AdminUIWidgetElement
  }

  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface HTMLElementEventMap extends AdminUIEventMap {}

  namespace JSX {
    interface IntrinsicElements {
      'context-management-widget': React.DetailedHTMLProps<
        React.HTMLAttributes<AdminUIWidgetElement> & AdminUIWidgetAttributes,
        AdminUIWidgetElement
      >
    }
  }
}

export {}
