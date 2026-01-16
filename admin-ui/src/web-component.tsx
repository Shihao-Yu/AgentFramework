import { createRoot, type Root } from 'react-dom/client'
import { AppConfigProvider, setGlobalConfig, type AppConfig } from './AppContext'
import { App } from './App'

import styles from './index.css?inline'
import reactFlowStyles from '@xyflow/react/dist/style.css?inline'

class AdminUIWidget extends HTMLElement {
  private root: Root | null = null
  private shadow: ShadowRoot
  private mountPoint: HTMLDivElement
  private styleElement: HTMLStyleElement

  static get observedAttributes() {
    return ['api-base-url', 'tenant-id', 'initial-route', 'theme']
  }

  constructor() {
    super()
    this.shadow = this.attachShadow({ mode: 'open' })

    this.styleElement = document.createElement('style')
    this.styleElement.textContent = this.buildStyles()
    this.shadow.appendChild(this.styleElement)

    this.mountPoint = document.createElement('div')
    this.mountPoint.id = 'admin-ui-root'
    this.mountPoint.style.cssText = 'height: 100%; width: 100%; position: relative;'
    this.shadow.appendChild(this.mountPoint)
  }

  private buildStyles(): string {
    return `
      ${styles}
      ${reactFlowStyles}
      
      :host {
        display: block;
        width: 100%;
        height: 100%;
        font-family: var(--font-sans);
      }
      
      #admin-ui-root {
        height: 100%;
        width: 100%;
        background-color: hsl(var(--background));
        color: hsl(var(--foreground));
      }
    `
  }

  connectedCallback() {
    this.renderReact()
    this.dispatchEvent(new CustomEvent('ready', { bubbles: true, composed: true }))
  }

  disconnectedCallback() {
    this.root?.unmount()
    this.root = null
  }

  attributeChangedCallback(name: string, oldValue: string | null, newValue: string | null) {
    if (oldValue !== newValue && this.root) {
      this.renderReact()
      this.dispatchEvent(new CustomEvent('config-changed', {
        detail: { attribute: name, oldValue, newValue },
        bubbles: true,
        composed: true,
      }))
    }
  }

  private getConfig(): AppConfig {
    const config: AppConfig = {
      apiBaseUrl: this.getAttribute('api-base-url') || '',
      tenantId: this.getAttribute('tenant-id') || 'default',
      initialRoute: this.getAttribute('initial-route') || '/',
      theme: (this.getAttribute('theme') as 'light' | 'dark' | 'system') || 'system',
      shadowRoot: this.shadow,
      hostElement: this,
      isWebComponent: true,
    }

    setGlobalConfig(config)
    return config
  }

  private renderReact() {
    const config = this.getConfig()

    if (!this.root) {
      this.root = createRoot(this.mountPoint)
    }

    this.root.render(
      <AppConfigProvider config={config}>
        <App />
      </AppConfigProvider>
    )
  }

  navigate(path: string) {
    const event = new CustomEvent('navigate-request', {
      detail: { path },
      bubbles: true,
      composed: true,
    })
    this.dispatchEvent(event)
  }

  refresh() {
    this.renderReact()
  }

  setTheme(theme: 'light' | 'dark' | 'system') {
    this.setAttribute('theme', theme)
  }
}

if (!customElements.get('context-management-widget')) {
  customElements.define('context-management-widget', AdminUIWidget)
}

export { AdminUIWidget }
export type { AppConfig }
