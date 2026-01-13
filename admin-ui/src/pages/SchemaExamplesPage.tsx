import { useState, useCallback, useMemo, useEffect } from 'react'
import { Plus, Trash2, FileCode, FileText, Pencil, Eye, Upload, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { SchemaEditor, ExampleFormDialog } from '@/components/schema'
import { SchemaImportDialog, QueryGeneratorPanel } from '@/components/datasets'
import { useSchemas } from '@/hooks/useSchemas'
import { useQueryForgeStatus, useDatasets } from '@/hooks/useQueryForge'
import { createEmptySchemaTemplate } from '@/lib/schemas/yamlSchemaV1'
import type { SchemaItem, ExampleItem, SchemaFormData, ExampleFormData } from '@/types/knowledge'
import type { QueryType } from '@/types/queryforge'
import { cn } from '@/lib/utils'

export function SchemaExamplesPage() {
  const {
    schemas,
    createSchema,
    updateSchema,
    deleteSchema,
    createExample,
    updateExample,
    deleteExample,
    getExamplesForSchema,
  } = useSchemas()

  const { status: queryForgeStatus, fetchStatus } = useQueryForgeStatus()
  const { onboardDataset } = useDatasets()

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  const [importDialogOpen, setImportDialogOpen] = useState(false)

  const [selectedSchemaId, setSelectedSchemaId] = useState<number | null>(
    schemas.length > 0 ? schemas[0].id : null
  )
  const [schemaDefinition, setSchemaDefinition] = useState<string>('')
  const [isSchemaModified, setIsSchemaModified] = useState(false)
  const [isSavingSchema, setIsSavingSchema] = useState(false)
  const [newSchemaDialogOpen, setNewSchemaDialogOpen] = useState(false)
  const [newSchemaName, setNewSchemaName] = useState('')
  const [newSchemaTitle, setNewSchemaTitle] = useState('')

  // Example state
  const [exampleFormOpen, setExampleFormOpen] = useState(false)
  const [editingExample, setEditingExample] = useState<ExampleItem | null>(null)
  const [viewExample, setViewExample] = useState<ExampleItem | null>(null)
  const [deleteExampleConfirmOpen, setDeleteExampleConfirmOpen] = useState(false)
  const [exampleToDelete, setExampleToDelete] = useState<ExampleItem | null>(null)

  // Delete schema state
  const [deleteSchemaConfirmOpen, setDeleteSchemaConfirmOpen] = useState(false)
  const [schemaToDelete, setSchemaToDelete] = useState<SchemaItem | null>(null)

  // Get selected schema
  const selectedSchema = useMemo(
    () => schemas.find((s) => s.id === selectedSchemaId) || null,
    [schemas, selectedSchemaId]
  )

  // Get examples for selected schema
  const schemaExamples = useMemo(
    () => (selectedSchemaId ? getExamplesForSchema(selectedSchemaId) : []),
    [selectedSchemaId, getExamplesForSchema]
  )

  useEffect(() => {
    if (selectedSchema && !schemaDefinition) {
      setSchemaDefinition(selectedSchema.content.definition)
    }
  }, [selectedSchema, schemaDefinition])

  const handleSelectSchema = useCallback((schema: SchemaItem) => {
    setSelectedSchemaId(schema.id)
    setSchemaDefinition(schema.content.definition)
    setIsSchemaModified(false)
  }, [])

  // Handle schema definition change
  const handleSchemaChange = useCallback(
    (value: string) => {
      setSchemaDefinition(value)
      setIsSchemaModified(value !== selectedSchema?.content.definition)
    },
    [selectedSchema]
  )

  // Save schema
  const handleSaveSchema = useCallback(async () => {
    if (!selectedSchema) return

    setIsSavingSchema(true)
    try {
      await updateSchema(selectedSchema.id, {
        title: selectedSchema.title,
        name: selectedSchema.content.name,
        definition: schemaDefinition,
        tags: selectedSchema.tags,
        status: selectedSchema.status,
        visibility: selectedSchema.visibility,
      })
      setIsSchemaModified(false)
    } finally {
      setIsSavingSchema(false)
    }
  }, [selectedSchema, schemaDefinition, updateSchema])

  // Create new schema
  const handleCreateSchema = useCallback(async () => {
    if (!newSchemaName || !newSchemaTitle) return

    const data: SchemaFormData = {
      title: newSchemaTitle,
      name: newSchemaName.toLowerCase().replace(/\s+/g, '-'),
      definition: createEmptySchemaTemplate(newSchemaName),
      tags: [],
      status: 'draft',
      visibility: 'internal',
    }

    const newSchema = await createSchema(data)
    setNewSchemaDialogOpen(false)
    setNewSchemaName('')
    setNewSchemaTitle('')
    handleSelectSchema(newSchema)
  }, [newSchemaName, newSchemaTitle, createSchema, handleSelectSchema])

  // Delete schema
  const handleDeleteSchemaConfirm = useCallback(async () => {
    if (schemaToDelete) {
      await deleteSchema(schemaToDelete.id)
      setDeleteSchemaConfirmOpen(false)
      setSchemaToDelete(null)

      // Select another schema if available
      const remaining = schemas.filter((s) => s.id !== schemaToDelete.id)
      if (remaining.length > 0) {
        handleSelectSchema(remaining[0])
      } else {
        setSelectedSchemaId(null)
        setSchemaDefinition('')
      }
    }
  }, [schemaToDelete, deleteSchema, schemas, handleSelectSchema])

  // Example handlers
  const handleCreateExample = useCallback(() => {
    setEditingExample(null)
    setExampleFormOpen(true)
  }, [])

  const handleEditExample = useCallback((example: ExampleItem) => {
    setEditingExample(example)
    setExampleFormOpen(true)
  }, [])

  const handleViewExample = useCallback((example: ExampleItem) => {
    setViewExample(example)
  }, [])

  const handleDeleteExampleClick = useCallback((example: ExampleItem) => {
    setExampleToDelete(example)
    setDeleteExampleConfirmOpen(true)
  }, [])

  const handleDeleteExampleConfirm = useCallback(async () => {
    if (exampleToDelete) {
      await deleteExample(exampleToDelete.id)
      setDeleteExampleConfirmOpen(false)
      setExampleToDelete(null)
    }
  }, [exampleToDelete, deleteExample])

  const handleExampleSubmit = useCallback(
    async (data: ExampleFormData) => {
      if (editingExample) {
        await updateExample(editingExample.id, data)
      } else {
        await createExample(data)
      }
    },
    [editingExample, createExample, updateExample]
  )

  const handleSaveAsExample = useCallback(
    async (question: string, query: string, queryType: QueryType, explanation?: string) => {
      if (!selectedSchemaId) return

      await createExample({
        title: question.slice(0, 50) + (question.length > 50 ? '...' : ''),
        schema_id: selectedSchemaId,
        description: explanation || question,
        content: query,
        format: queryType === 'elasticsearch' ? 'json' : 'text',
        tags: ['generated', queryType],
        status: 'draft',
        visibility: 'internal',
      })
    },
    [selectedSchemaId, createExample]
  )

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Datasets</h1>
          <p className="text-muted-foreground">
            Manage data schemas and query examples for AI-powered query generation.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {queryForgeStatus?.available && (
            <Badge variant="outline" className="text-xs text-green-600 border-green-600">
              <Sparkles className="h-3 w-3 mr-1" />
              QueryForge Active
            </Badge>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Dataset
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setNewSchemaDialogOpen(true)}>
                <FileCode className="mr-2 h-4 w-4" />
                Create Manually
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setImportDialogOpen(true)}>
                <Upload className="mr-2 h-4 w-4" />
                Import from Schema
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-3">
          <Card className="h-[calc(100vh-220px)]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Datasets</CardTitle>
              <CardDescription className="text-xs">
                {schemas.length} dataset{schemas.length !== 1 ? 's' : ''}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <ScrollArea className="h-[calc(100vh-320px)]">
                <div className="space-y-1 p-2">
                  {schemas.map((schema) => (
                    <div
                      key={schema.id}
                      className={cn(
                        'flex items-center justify-between p-2 rounded-md cursor-pointer hover:bg-muted/50',
                        selectedSchemaId === schema.id && 'bg-muted'
                      )}
                      onClick={() => handleSelectSchema(schema)}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileCode className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <div className="min-w-0">
                          <div className="font-medium text-sm truncate">
                            {schema.title}
                          </div>
                          <div className="text-xs text-muted-foreground truncate">
                            {schema.content.name}
                          </div>
                        </div>
                      </div>
                      <Badge
                        variant={schema.status === 'published' ? 'success' : 'secondary'}
                        className="text-xs shrink-0"
                      >
                        {schema.status}
                      </Badge>
                    </div>
                  ))}
                  {schemas.length === 0 && (
                    <div className="text-center text-muted-foreground text-sm py-8">
                      No schemas yet
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>

        {/* Schema Editor & Examples - Main Content */}
        <div className="col-span-9">
          {selectedSchema ? (
            <Tabs defaultValue="editor" className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-semibold">{selectedSchema.title}</h2>
                  <p className="text-sm text-muted-foreground">
                    {selectedSchema.content.name} - {schemaExamples.length} example
                    {schemaExamples.length !== 1 ? 's' : ''}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <TabsList>
                    <TabsTrigger value="editor">Schema</TabsTrigger>
                    <TabsTrigger value="examples">
                      Examples ({schemaExamples.length})
                    </TabsTrigger>
                    {queryForgeStatus?.available && (
                      <TabsTrigger value="query">
                        <Sparkles className="h-3.5 w-3.5 mr-1" />
                        Query
                      </TabsTrigger>
                    )}
                  </TabsList>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => {
                      setSchemaToDelete(selectedSchema)
                      setDeleteSchemaConfirmOpen(true)
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <TabsContent value="editor" className="mt-4">
                <Card>
                  <CardContent className="pt-6">
                    <SchemaEditor
                      value={schemaDefinition}
                      onChange={handleSchemaChange}
                      onSave={handleSaveSchema}
                      isSaving={isSavingSchema}
                    />
                    {isSchemaModified && (
                      <p className="text-sm text-amber-600 mt-2">
                        You have unsaved changes
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="examples" className="mt-4">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between">
                    <div>
                      <CardTitle>Examples</CardTitle>
                      <CardDescription>
                        Q&A training pairs for query generation
                      </CardDescription>
                    </div>
                    <Button onClick={handleCreateExample} size="sm">
                      <Plus className="mr-2 h-4 w-4" />
                      Add Example
                    </Button>
                  </CardHeader>
                  <CardContent>
                    {schemaExamples.length > 0 ? (
                      <div className="space-y-3">
                        {schemaExamples.map((example) => (
                          <div
                            key={example.id}
                            className="flex items-center justify-between p-3 border rounded-lg"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <FileText className="h-5 w-5 shrink-0 text-muted-foreground" />
                              <div className="min-w-0">
                                <div className="font-medium truncate">
                                  {example.title}
                                </div>
                                <div className="text-sm text-muted-foreground truncate">
                                  {example.content.description}
                                </div>
                                <div className="flex gap-1 mt-1">
                                  <Badge variant="outline" className="text-xs">
                                    {example.content.format}
                                  </Badge>
                                  <Badge
                                    variant={
                                      example.status === 'published'
                                        ? 'success'
                                        : 'secondary'
                                    }
                                    className="text-xs"
                                  >
                                    {example.status}
                                  </Badge>
                                </div>
                              </div>
                            </div>
                            <div className="flex gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleViewExample(example)}
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleEditExample(example)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteExampleClick(example)}
                                className="text-destructive hover:text-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-muted-foreground">
                        No examples yet. Add Q&A pairs to improve query generation.
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {queryForgeStatus?.available && (
                <TabsContent value="query" className="mt-4">
                  <QueryGeneratorPanel
                    datasetName={selectedSchema.content.name}
                    tenantId="default"
                    onSaveAsExample={handleSaveAsExample}
                  />
                </TabsContent>
              )}
            </Tabs>
          ) : (
            <Card className="h-[calc(100vh-220px)] flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <FileCode className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a schema or create a new one</p>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* New Schema Dialog */}
      <Dialog open={newSchemaDialogOpen} onOpenChange={setNewSchemaDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Schema</DialogTitle>
            <DialogDescription>
              Enter the details for your new schema definition.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="schema-title">Title</Label>
              <Input
                id="schema-title"
                placeholder="e.g., Purchase Orders Schema"
                value={newSchemaTitle}
                onChange={(e) => setNewSchemaTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="schema-name">Name (identifier)</Label>
              <Input
                id="schema-name"
                placeholder="e.g., purchase-orders"
                value={newSchemaName}
                onChange={(e) => setNewSchemaName(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Lowercase, alphanumeric with dashes. Used as tenant_id.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNewSchemaDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateSchema}
              disabled={!newSchemaName || !newSchemaTitle}
            >
              Create Schema
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Schema Confirmation */}
      <Dialog open={deleteSchemaConfirmOpen} onOpenChange={setDeleteSchemaConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Schema</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{schemaToDelete?.title}"? This will also
              delete all associated examples. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteSchemaConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteSchemaConfirm}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Example Form Dialog */}
      <ExampleFormDialog
        open={exampleFormOpen}
        onOpenChange={setExampleFormOpen}
        item={editingExample}
        schemas={schemas}
        defaultSchemaId={selectedSchemaId || undefined}
        onSubmit={handleExampleSubmit}
      />

      {/* View Example Dialog */}
      <Dialog open={!!viewExample} onOpenChange={() => setViewExample(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{viewExample?.title}</DialogTitle>
            <DialogDescription>{viewExample?.content.description}</DialogDescription>
          </DialogHeader>
          {viewExample && (
            <div className="space-y-4">
              <div>
                <Label className="text-sm text-muted-foreground">Content</Label>
                <pre className="mt-1 p-3 bg-muted rounded-md text-sm overflow-auto max-h-[300px]">
                  {viewExample.content.content}
                </pre>
              </div>
              <div className="flex gap-2">
                <Badge variant="outline">{viewExample.content.format}</Badge>
                {viewExample.tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewExample(null)}>
              Close
            </Button>
            <Button
              onClick={() => {
                if (viewExample) {
                  handleEditExample(viewExample)
                  setViewExample(null)
                }
              }}
            >
              Edit
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Example Confirmation */}
      <Dialog
        open={deleteExampleConfirmOpen}
        onOpenChange={setDeleteExampleConfirmOpen}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Example</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{exampleToDelete?.title}"? This action
              cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteExampleConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteExampleConfirm}>
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <SchemaImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        onImport={onboardDataset}
        tenantId="default"
        availableSources={queryForgeStatus?.available_sources}
      />
    </div>
  )
}
