import { BrowserRouter, MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TenantProvider } from '@/components/tenant/TenantProvider'
import { AppLayout } from '@/components/layout/AppLayout'
import { FAQPage } from '@/pages/FAQPage'
import { PermissionsPage } from '@/pages/PermissionsPage'
import { SchemaExamplesPage } from '@/pages/SchemaExamplesPage'
import { PlaybooksPage } from '@/pages/PlaybooksPage'
import { StagingQueuePage } from '@/pages/StagingQueuePage'
import { MetricsDashboardPage } from '@/pages/MetricsDashboardPage'
import { GraphAnalyticsPage } from '@/pages/GraphAnalyticsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { GraphExplorerPage } from '@/pages/GraphExplorerPage'
import { EntitiesPage } from '@/pages/EntitiesPage'
import { ConceptsPage } from '@/pages/ConceptsPage'
import { useAppConfig } from '@/AppContext'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
})

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<AppLayout />}>
        <Route index element={<FAQPage />} />
        <Route path="graph" element={<GraphExplorerPage />} />
        <Route path="permissions" element={<PermissionsPage />} />
        <Route path="schemas" element={<SchemaExamplesPage />} />
        <Route path="playbooks" element={<PlaybooksPage />} />
        <Route path="entities" element={<EntitiesPage />} />
        <Route path="concepts" element={<ConceptsPage />} />
        <Route path="staging" element={<StagingQueuePage />} />
        <Route path="analytics" element={<MetricsDashboardPage />} />
        <Route path="graph-analytics" element={<GraphAnalyticsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

function AppWithRouter() {
  const { isWebComponent, initialRoute, tenantId } = useAppConfig()

  const routes = <AppRoutes />

  if (isWebComponent) {
    return (
      <QueryClientProvider client={queryClient}>
        <TenantProvider defaultTenantId={tenantId}>
          <MemoryRouter initialEntries={[initialRoute]}>
            {routes}
          </MemoryRouter>
        </TenantProvider>
      </QueryClientProvider>
    )
  }

  return (
    <QueryClientProvider client={queryClient}>
      <TenantProvider defaultTenantId={tenantId}>
        <BrowserRouter>
          {routes}
        </BrowserRouter>
      </TenantProvider>
    </QueryClientProvider>
  )
}

export function App() {
  return <AppWithRouter />
}

export default App
