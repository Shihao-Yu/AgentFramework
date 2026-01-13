export type SourceType = 'postgres' | 'opensearch' | 'rest_api' | 'clickhouse'
export type QueryType = 'sql' | 'elasticsearch' | 'api'

export interface QueryForgeStatus {
  available: boolean
  available_sources: SourceType[]
  error?: string
  install_hint?: string
}

export interface DatasetSummary {
  id: number
  dataset_name: string
  source_type: SourceType
  description: string
  tags: string[]
  status: string
  created_at?: string
}

export interface DatasetDetail extends DatasetSummary {
  tenant_id: string
  field_count: number
  example_count: number
  verified_example_count: number
  updated_at?: string
}

export interface DatasetOnboardRequest {
  tenant_id: string
  dataset_name: string
  source_type: SourceType
  raw_schema: string
  description?: string
  tags?: string[]
  enable_enrichment?: boolean
}

export interface DatasetOnboardResponse {
  status: 'success' | 'error'
  dataset_name?: string
  source_type?: string
  schema_index_id?: number
  field_count?: number
  fields?: number[]
  error?: string
  errors?: string[]
}

export interface DatasetDeleteResponse {
  status: 'success' | 'error'
  deleted_nodes?: number
  deleted_edges?: number
  error?: string
}

export interface QueryGenerateRequest {
  tenant_id: string
  dataset_name: string
  question: string
  include_explanation?: boolean
}

export interface QueryGenerateResponse {
  status: 'success' | 'error'
  query?: string
  query_type?: QueryType
  explanation?: string
  confidence?: number
  error?: string
}

export interface DatasetExample {
  id: number
  question: string
  query: string
  query_type: QueryType
  explanation?: string
  verified: boolean
  dataset_name?: string
  created_at?: string
}

export interface ExampleCreateRequest {
  tenant_id: string
  dataset_name: string
  question: string
  query: string
  query_type: QueryType
  explanation?: string
  verified?: boolean
}

export interface ExampleVerifyRequest {
  verified: boolean
}

export interface ExampleVerifyResponse {
  status: 'success' | 'error'
  example_id?: number
  verified?: boolean
  error?: string
}

export const SOURCE_TYPE_LABELS: Record<SourceType, string> = {
  postgres: 'PostgreSQL',
  opensearch: 'OpenSearch',
  rest_api: 'REST API',
  clickhouse: 'ClickHouse',
}

export const SOURCE_TYPE_PLACEHOLDERS: Record<SourceType, string> = {
  postgres: `CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER REFERENCES customers(id),
  status VARCHAR(50) DEFAULT 'pending',
  amount DECIMAL(10,2),
  created_at TIMESTAMP DEFAULT NOW()
);`,
  opensearch: `{
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "status": { "type": "keyword" },
      "created_at": { "type": "date" }
    }
  }
}`,
  rest_api: `openapi: 3.0.0
info:
  title: Orders API
  version: 1.0.0
paths:
  /orders:
    get:
      summary: List orders
      parameters:
        - name: status
          in: query
          schema:
            type: string`,
  clickhouse: `CREATE TABLE orders (
  id UInt64,
  customer_id UInt64,
  status String,
  amount Decimal(10,2),
  created_at DateTime
) ENGINE = MergeTree()
ORDER BY id;`,
}

export const QUERY_TYPE_LABELS: Record<QueryType, string> = {
  sql: 'SQL',
  elasticsearch: 'OpenSearch DSL',
  api: 'API Request',
}
