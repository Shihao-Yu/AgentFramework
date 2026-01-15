import { useState, useMemo, useEffect } from 'react'
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { ArrowUpDown, MoreHorizontal, Search, Plus, Eye, Pencil, Trash2, Network } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MultiSelect } from '@/components/ui/multi-select'

import type { KnowledgeNode, NodeType } from '@/types/graph'
import { NodeTypeLabels, NodeTypeConfig, NodeStatus as NodeStatusEnum } from '@/types/graph'

interface PaginationInfo {
  page: number
  limit: number
  total: number
  totalPages: number
}

interface NodeListProps {
  nodes: KnowledgeNode[]
  nodeType?: NodeType
  allTags: string[]
  pagination: PaginationInfo
  selectedTags: string[]
  searchValue: string
  isLoading?: boolean
  onView?: (node: KnowledgeNode) => void
  onEdit?: (node: KnowledgeNode) => void
  onDelete?: (node: KnowledgeNode) => void
  onViewInGraph?: (node: KnowledgeNode) => void
  onCreate?: () => void
  onSearchChange: (search: string) => void
  onTagsChange: (tags: string[]) => void
  onPageChange: (page: number) => void
  title?: string
  description?: string
}

function getColumns(
  onView?: (node: KnowledgeNode) => void,
  onEdit?: (node: KnowledgeNode) => void,
  onDelete?: (node: KnowledgeNode) => void,
  onViewInGraph?: (node: KnowledgeNode) => void
): ColumnDef<KnowledgeNode>[] {
  return [
    {
      accessorKey: 'title',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Title
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const node = row.original
        const config = NodeTypeConfig[node.node_type]
        return (
          <div className="flex items-center gap-2">
            <span>{config.icon}</span>
            <div>
              <span className="font-medium">{node.title}</span>
              {node.summary && (
                <p className="text-xs text-muted-foreground line-clamp-1">{node.summary}</p>
              )}
            </div>
          </div>
        )
      },
    },
    {
      accessorKey: 'node_type',
      header: 'Type',
      cell: ({ row }) => {
        const nodeType = row.original.node_type
        const config = NodeTypeConfig[nodeType]
        return (
          <Badge
            variant="outline"
            style={{ borderColor: config.color, color: config.color }}
          >
            {NodeTypeLabels[nodeType]}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => {
        const status = row.original.status
        return (
          <Badge
            variant={
              status === 'published'
                ? 'default'
                : status === 'draft'
                ? 'secondary'
                : 'outline'
            }
          >
            {status}
          </Badge>
        )
      },
    },
    {
      accessorKey: 'tags',
      header: 'Tags',
      cell: ({ row }) => {
        const tags = row.original.tags
        return (
          <div className="flex flex-wrap gap-1">
            {tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
            {tags.length > 3 && (
              <span className="text-xs text-muted-foreground">+{tags.length - 3}</span>
            )}
          </div>
        )
      },
    },
    {
      accessorKey: 'tenant_id',
      header: 'Tenant',
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">{row.original.tenant_id}</span>
      ),
    },
    {
      accessorKey: 'updated_at',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
        >
          Updated
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const date = row.original.updated_at || row.original.created_at
        return (
          <span className="text-sm text-muted-foreground">
            {new Date(date).toLocaleDateString()}
          </span>
        )
      },
    },
    {
      id: 'actions',
      cell: ({ row }) => {
        const node = row.original

        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-8 w-8 p-0">
                <span className="sr-only">Open menu</span>
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Actions</DropdownMenuLabel>
              {onView && (
                <DropdownMenuItem onClick={() => onView(node)}>
                  <Eye className="mr-2 h-4 w-4" />
                  View
                </DropdownMenuItem>
              )}
              {onEdit && (
                <DropdownMenuItem onClick={() => onEdit(node)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
              )}
              {onViewInGraph && (
                <DropdownMenuItem onClick={() => onViewInGraph(node)}>
                  <Network className="mr-2 h-4 w-4" />
                  View in Graph
                </DropdownMenuItem>
              )}
              {onDelete && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={() => onDelete(node)}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        )
      },
    },
  ]
}

export function NodeList({
  nodes,
  nodeType,
  allTags,
  pagination,
  selectedTags,
  searchValue,
  isLoading,
  onView,
  onEdit,
  onDelete,
  onViewInGraph,
  onCreate,
  onSearchChange,
  onTagsChange,
  onPageChange,
  title,
  description,
}: NodeListProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [localSearch, setLocalSearch] = useState(searchValue)

  // Sync local search with prop
  useEffect(() => {
    setLocalSearch(searchValue)
  }, [searchValue])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localSearch !== searchValue) {
        onSearchChange(localSearch)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [localSearch, searchValue, onSearchChange])

  const columns = useMemo(
    () => getColumns(onView, onEdit, onDelete, onViewInGraph),
    [onView, onEdit, onDelete, onViewInGraph]
  )

  const table = useReactTable({
    data: nodes,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    manualPagination: true,
    pageCount: pagination.totalPages,
    state: {
      sorting,
      pagination: {
        pageIndex: pagination.page - 1,
        pageSize: pagination.limit,
      },
    },
  })

  const pageTitle = title || (nodeType ? NodeTypeLabels[nodeType] + 's' : 'All Nodes')
  const pageDescription = description || `Manage ${nodeType ? NodeTypeLabels[nodeType].toLowerCase() : 'knowledge'} nodes`

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">{pageTitle}</h2>
          <p className="text-sm text-muted-foreground">{pageDescription}</p>
        </div>
        {onCreate && (
          <Button onClick={onCreate}>
            <Plus className="mr-2 h-4 w-4" />
            Create New
          </Button>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search..."
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <MultiSelect
          options={allTags}
          selected={selectedTags}
          onChange={onTagsChange}
          placeholder="Filter by tags..."
          className="w-[200px]"
        />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id} data-state={row.getIsSelected() && 'selected'}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  No results found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-muted-foreground">
          {pagination.total} node(s) total
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(pagination.page - 1)}
            disabled={pagination.page <= 1}
          >
            Previous
          </Button>
          <div className="text-sm">
            Page {pagination.page} of {pagination.totalPages || 1}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(pagination.page + 1)}
            disabled={pagination.page >= pagination.totalPages}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
