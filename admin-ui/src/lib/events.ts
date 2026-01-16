import { getGlobalConfig } from '@/AppContext'

export type AdminUIEventType = 
  | 'ready'
  | 'config-changed'
  | 'route-changed'
  | 'navigate-request'
  | 'faq-created'
  | 'faq-updated'
  | 'faq-deleted'
  | 'node-selected'
  | 'error'

export interface AdminUIEventPayloads {
  ready: Record<string, never>
  'config-changed': { attribute: string; oldValue: string | null; newValue: string | null }
  'route-changed': { path: string }
  'navigate-request': { path: string }
  'faq-created': { id: number; title: string }
  'faq-updated': { id: number; title: string }
  'faq-deleted': { id: number }
  'node-selected': { id: number; type: string } | null
  error: { message: string; code?: string }
}

export function emitEvent<T extends AdminUIEventType>(
  eventType: T,
  payload: AdminUIEventPayloads[T]
): void {
  const config = getGlobalConfig()
  
  if (!config.isWebComponent || !config.hostElement) {
    console.debug(`[AdminUI Event] ${eventType}:`, payload)
    return
  }
  
  const event = new CustomEvent(eventType, {
    detail: payload,
    bubbles: true,
    composed: true,
  })
  
  config.hostElement.dispatchEvent(event)
}

export function emitError(message: string, code?: string): void {
  emitEvent('error', { message, code })
}

export function emitRouteChange(path: string): void {
  emitEvent('route-changed', { path })
}
