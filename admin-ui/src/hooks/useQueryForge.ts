import { useState, useCallback } from 'react'
import { apiRequest } from '@/lib/api'
import type {
  QueryForgeStatus,
  DatasetDetail,
  DatasetSummary,
  DatasetOnboardRequest,
  DatasetOnboardResponse,
  QueryGenerateRequest,
  QueryGenerateResponse,
  DatasetExample,
  ExampleCreateRequest,
  SourceType,
} from '@/types/queryforge'

interface ExampleListResponse {
  examples: DatasetExample[]
  total: number
}

interface ExampleVerifyResponse {
  status: 'success' | 'error'
  example_id?: number
  verified?: boolean
  error?: string
}

export function useQueryForgeStatus() {
  const [status, setStatus] = useState<QueryForgeStatus | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<QueryForgeStatus>('/api/datasets/status')
      setStatus(response)
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch QueryForge status'
      setError(message)
      console.error('Failed to fetch QueryForge status:', err)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { status, isLoading, error, fetchStatus }
}

export function useDatasets(tenantId: string = 'default') {
  const [datasets, setDatasets] = useState<DatasetDetail[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDatasets = useCallback(async (sourceType?: SourceType) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | number | undefined> = {
        tenant_id: tenantId,
        limit: 100,
      }
      
      if (sourceType) {
        params.source_type = sourceType
      }
      
      const response = await apiRequest<DatasetSummary[]>('/api/datasets', { params })
      
      // Convert DatasetSummary to DatasetDetail (some fields may be missing)
      const detailedDatasets: DatasetDetail[] = response.map(d => ({
        ...d,
        tenant_id: tenantId,
        field_count: 0, // Will be populated when fetching individual dataset
        example_count: 0,
        verified_example_count: 0,
      }))
      
      setDatasets(detailedDatasets)
      return detailedDatasets
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch datasets'
      setError(message)
      console.error('Failed to fetch datasets:', err)
      return []
    } finally {
      setIsLoading(false)
    }
  }, [tenantId])

  const getDataset = useCallback(async (datasetName: string): Promise<DatasetDetail | null> => {
    try {
      const response = await apiRequest<DatasetDetail>(`/api/datasets/${datasetName}`, {
        params: { tenant_id: tenantId },
      })
      return response
    } catch (err) {
      console.error(`Failed to fetch dataset ${datasetName}:`, err)
      return null
    }
  }, [tenantId])

  const onboardDataset = useCallback(async (request: DatasetOnboardRequest): Promise<DatasetOnboardResponse> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<DatasetOnboardResponse>('/api/datasets/onboard', {
        method: 'POST',
        body: JSON.stringify(request),
      })
      
      if (response.status === 'success') {
        // Refresh the datasets list
        await fetchDatasets()
      }
      
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to onboard dataset'
      setError(message)
      
      return {
        status: 'error',
        error: message,
      }
    } finally {
      setIsLoading(false)
    }
  }, [fetchDatasets])

  const deleteDataset = useCallback(async (datasetName: string) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<{
        status: string
        dataset_name: string
        deleted_nodes: number
      }>(`/api/datasets/${datasetName}`, {
        method: 'DELETE',
        params: { tenant_id: tenantId },
      })
      
      // Update local state
      setDatasets(prev => prev.filter(d => d.dataset_name !== datasetName))
      
      return {
        status: 'success' as const,
        deleted_nodes: response.deleted_nodes,
        deleted_edges: 0,
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete dataset'
      setError(message)
      
      return {
        status: 'error' as const,
        error: message,
      }
    } finally {
      setIsLoading(false)
    }
  }, [tenantId])

  return {
    datasets,
    isLoading,
    error,
    fetchDatasets,
    getDataset,
    onboardDataset,
    deleteDataset,
  }
}

export function useQueryGeneration() {
  const [isGenerating, setIsGenerating] = useState(false)
  const [lastResult, setLastResult] = useState<QueryGenerateResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const generateQuery = useCallback(async (request: QueryGenerateRequest): Promise<QueryGenerateResponse> => {
    setIsGenerating(true)
    setError(null)
    
    try {
      const response = await apiRequest<QueryGenerateResponse>('/api/datasets/generate', {
        method: 'POST',
        body: JSON.stringify(request),
      })
      
      setLastResult(response)
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to generate query'
      setError(message)
      
      const result: QueryGenerateResponse = {
        status: 'error',
        error: message,
      }
      setLastResult(result)
      return result
    } finally {
      setIsGenerating(false)
    }
  }, [])

  return { generateQuery, isGenerating, lastResult, error }
}

export function useDatasetExamples(datasetName?: string, tenantId: string = 'default') {
  const [examples, setExamples] = useState<DatasetExample[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchExamples = useCallback(async (name?: string, verifiedOnly: boolean = false) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const params: Record<string, string | boolean | number | undefined> = {
        tenant_id: tenantId,
        limit: 100,
      }
      
      if (name || datasetName) {
        params.dataset_name = name || datasetName
      }
      if (verifiedOnly) {
        params.verified_only = true
      }
      
      const response = await apiRequest<ExampleListResponse>('/api/datasets/examples', { params })
      setExamples(response.examples)
      return response.examples
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch examples'
      setError(message)
      console.error('Failed to fetch examples:', err)
      return []
    } finally {
      setIsLoading(false)
    }
  }, [datasetName, tenantId])

  const createExample = useCallback(async (request: ExampleCreateRequest): Promise<DatasetExample> => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<DatasetExample>('/api/datasets/examples', {
        method: 'POST',
        body: JSON.stringify(request),
      })
      
      setExamples(prev => [...prev, response])
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create example'
      setError(message)
      throw err
    } finally {
      setIsLoading(false)
    }
  }, [])

  const verifyExample = useCallback(async (exampleId: number, verified: boolean) => {
    setIsLoading(true)
    setError(null)
    
    try {
      const response = await apiRequest<ExampleVerifyResponse>(
        `/api/datasets/examples/${exampleId}/verify`,
        {
          method: 'PATCH',
          body: JSON.stringify({ verified }),
        }
      )
      
      if (response.status === 'success') {
        setExamples(prev => prev.map(e => 
          e.id === exampleId ? { ...e, verified } : e
        ))
      }
      
      return response
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to verify example'
      setError(message)
      
      return {
        status: 'error' as const,
        error: message,
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  const deleteExample = useCallback(async (exampleId: number) => {
    setIsLoading(true)
    setError(null)
    
    try {
      // Note: The backend doesn't have a delete example endpoint yet
      // This will need to be added or use the node delete endpoint
      await apiRequest(`/api/nodes/${exampleId}`, {
        method: 'DELETE',
      })
      
      setExamples(prev => prev.filter(e => e.id !== exampleId))
      return true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete example'
      setError(message)
      console.error('Failed to delete example:', err)
      return false
    } finally {
      setIsLoading(false)
    }
  }, [])

  return {
    examples,
    isLoading,
    error,
    fetchExamples,
    createExample,
    verifyExample,
    deleteExample,
  }
}
