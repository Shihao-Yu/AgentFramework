import { useState, useMemo, useEffect } from 'react'
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { MoreHorizontal, ArrowUpDown, Eye, Pencil, Trash2, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
import { MultiSelect } from '@/components/ui/multi-select'
import type { PlaybookItem, Domain } from '@/types/knowledge'
import { format } from 'date-fns'

interface PaginationInfo {
  page: number
  limit: number
  total: number
  totalPages: number
}

interface PlaybookDataTableProps {
  data: PlaybookItem[]
  domains: Domain[]
  allTags: string[]
  pagination: PaginationInfo
  selectedTags: string[]
  searchValue: string
  isLoading?: boolean
  onView: (item: PlaybookItem) => void
  onEdit: (item: PlaybookItem) => void
  onDelete: (item: PlaybookItem) => void
  onSearchChange: (search: string) => void
  onTagsChange: (tags: string[]) => void
  onPageChange: (page: number) => void
}

export function PlaybookDataTable({
  data,
  domains,
  allTags,
  pagination,
  selectedTags,
  searchValue,
  isLoading,
  onView,
  onEdit,
  onDelete,
  onSearchChange,
  onTagsChange,
  onPageChange,
}: PlaybookDataTableProps) {
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

  const getDomainName = (domainId: string) => {
    const domain = domains.find((d) => d.id === domainId)
    return domain?.name || domainId
  }

  const columns: ColumnDef<PlaybookItem>[] = useMemo(
    () => [
      {
        accessorKey: 'title',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="-ml-4"
          >
            Title
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: ({ row }) => {
          const item = row.original
          return (
            <div className="max-w-md">
              <div className="font-medium">{item.title}</div>
            </div>
          )
        },
      },
      {
        accessorKey: 'content.domain',
        header: 'Domain',
        cell: ({ row }) => {
          const domain = row.original.content.domain
          return (
            <Badge variant="outline" className="capitalize">
              {getDomainName(domain)}
            </Badge>
          )
        },
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const status = row.getValue('status') as string
          const variants: Record<
            string,
            'default' | 'secondary' | 'success' | 'warning' | 'destructive'
          > = {
            published: 'success',
            draft: 'secondary',
            archived: 'warning',
          }
          return (
            <Badge variant={variants[status] || 'secondary'} className="capitalize">
              {status}
            </Badge>
          )
        },
      },
      {
        accessorKey: 'tags',
        header: 'Tags',
        cell: ({ row }) => {
          const tags = row.getValue('tags') as string[]
          const displayTags = tags.slice(0, 3)
          const remaining = tags.length - 3
          return (
            <div className="flex flex-wrap gap-1">
              {displayTags.map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {remaining > 0 && (
                <Badge variant="outline" className="text-xs">
                  +{remaining}
                </Badge>
              )}
            </div>
          )
        },
      },
      {
        accessorKey: 'updated_at',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="-ml-4"
          >
            Updated
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: ({ row }) => {
          const date = row.getValue('updated_at') as string
          if (!date) return <span className="text-muted-foreground">-</span>
          return (
            <div className="text-sm text-muted-foreground">
              {format(new Date(date), 'MMM d, yyyy')}
            </div>
          )
        },
      },
      {
        id: 'actions',
        enableHiding: false,
        cell: ({ row }) => {
          const item = row.original
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
                <DropdownMenuItem onClick={() => onView(item)}>
                  <Eye className="mr-2 h-4 w-4" />
                  View
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onEdit(item)}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => onDelete(item)}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )
        },
      },
    ],
    [domains, onView, onEdit, onDelete]
  )

  const table = useReactTable({
    data,
    columns,
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
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

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search playbooks..."
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
                <TableRow key={row.id}>
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
                  No playbooks found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-muted-foreground">
          {pagination.total} playbook(s) total
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
