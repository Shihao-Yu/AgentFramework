import { createContext, useContext, useEffect, type ReactNode } from 'react'

/**
 * Configuration for the Admin UI when running as a web component.
 * These values are passed from the custom element attributes.
 */
export interface AppConfig {
  /** Backend API base URL (e.g., "https://api.example.com") */
  apiBaseUrl: string
  /** Tenant identifier for multi-tenant setups */
  tenantId: string
  /** Initial route to display (e.g., "/", "/graph", "/faqs") */
  initialRoute: string
  /** Color theme */
  theme: 'light' | 'dark' | 'system'
  /** Shadow root reference when running as web component (null for standalone) */
  shadowRoot: ShadowRoot | null
  /** Host custom element reference for event dispatching */
  hostElement: HTMLElement | null
  /** Whether running in web component mode */
  isWebComponent: boolean
}

const defaultConfig: AppConfig = {
  apiBaseUrl: import.meta.env.VITE_API_URL || '',
  tenantId: 'purchasing',
  initialRoute: '/',
  theme: 'system',
  shadowRoot: null,
  hostElement: null,
  isWebComponent: false,
}

const AppConfigContext = createContext<AppConfig>(defaultConfig)

interface AppConfigProviderProps {
  config: Partial<AppConfig>
  children: ReactNode
}

export function AppConfigProvider({ config, children }: AppConfigProviderProps) {
  const mergedConfig: AppConfig = { ...defaultConfig, ...config }
  
  // Apply theme to the shadow root or document
  useEffect(() => {
    const applyTheme = (theme: 'light' | 'dark') => {
      const root = mergedConfig.shadowRoot?.host || document.documentElement
      if (root instanceof HTMLElement) {
        if (theme === 'dark') {
          root.classList.add('dark')
          root.classList.remove('light')
        } else {
          root.classList.add('light')
          root.classList.remove('dark')
        }
      }
    }

    if (mergedConfig.theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      applyTheme(mediaQuery.matches ? 'dark' : 'light')
      
      const handler = (e: MediaQueryListEvent) => applyTheme(e.matches ? 'dark' : 'light')
      mediaQuery.addEventListener('change', handler)
      return () => mediaQuery.removeEventListener('change', handler)
    } else {
      applyTheme(mergedConfig.theme)
    }
  }, [mergedConfig.theme, mergedConfig.shadowRoot])
  
  return (
    <AppConfigContext.Provider value={mergedConfig}>
      {children}
    </AppConfigContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAppConfig(): AppConfig {
  return useContext(AppConfigContext)
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePortalContainer(): HTMLElement {
  const { shadowRoot } = useAppConfig()
  
  if (shadowRoot) {
    // Find or create a portal container inside shadow DOM
    let portalContainer = shadowRoot.getElementById('portal-container')
    if (!portalContainer) {
      portalContainer = document.createElement('div')
      portalContainer.id = 'portal-container'
      portalContainer.style.position = 'absolute'
      portalContainer.style.top = '0'
      portalContainer.style.left = '0'
      portalContainer.style.zIndex = '9999'
      shadowRoot.appendChild(portalContainer)
    }
    return portalContainer
  }
  
  return document.body
}

// eslint-disable-next-line react-refresh/only-export-components
export function useEmitEvent() {
  const { hostElement, isWebComponent } = useAppConfig()
  
  return (eventName: string, detail?: unknown) => {
    if (!isWebComponent || !hostElement) {
      // In standalone mode, just log for debugging
      console.debug(`[AdminUI Event] ${eventName}:`, detail)
      return
    }
    
    const event = new CustomEvent(eventName, {
      detail,
      bubbles: true,
      composed: true, // Crosses shadow DOM boundary
    })
    hostElement.dispatchEvent(event)
  }
}

let globalConfig: AppConfig = defaultConfig

// eslint-disable-next-line react-refresh/only-export-components
export function setGlobalConfig(config: Partial<AppConfig>) {
  globalConfig = { ...defaultConfig, ...config }
}

// eslint-disable-next-line react-refresh/only-export-components
export function getGlobalConfig(): AppConfig {
  return globalConfig
}
