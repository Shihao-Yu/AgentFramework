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
import type { PermissionItem } from '@/types/knowledge'
import { format } from 'date-fns'

interface PaginationInfo {
  page: number
  limit: number
  total: number
  totalPages: number
}

interface PermissionDataTableProps {
  data: PermissionItem[]
  allTags: string[]
  pagination: PaginationInfo
  selectedTags: string[]
  searchValue: string
  isLoading?: boolean
  onView: (item: PermissionItem) => void
  onEdit: (item: PermissionItem) => void
  onDelete: (item: PermissionItem) => void
  onSearchChange: (search: string) => void
  onTagsChange: (tags: string[]) => void
  onPageChange: (page: number) => void
}

export function PermissionDataTable({
  data,
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
}: PermissionDataTableProps) {
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

  const columns: ColumnDef<PermissionItem>[] = useMemo(
    () => [
      {
        accessorKey: 'title',
        header: ({ column }) => (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
            className="-ml-4"
          >
            Feature
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        ),
        cell: ({ row }) => {
          const item = row.original
          return (
            <div className="max-w-md">
              <div className="font-medium">{item.title}</div>
              <div className="text-sm text-muted-foreground line-clamp-1">
                {item.content.description}
              </div>
            </div>
          )
        },
      },
      {
        accessorKey: 'content.permissions',
        header: 'Permissions',
        cell: ({ row }) => {
          const permissions = row.original.content.permissions
          const displayItems = permissions.slice(0, 2)
          const remaining = permissions.length - 2
          return (
            <div className="flex flex-wrap gap-1">
              {displayItems.map((permission) => (
                <Badge key={permission} variant="default" className="text-xs font-mono">
                  {permission}
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
        accessorKey: 'content.roles',
        header: 'Roles',
        cell: ({ row }) => {
          const roles = row.original.content.roles
          const displayItems = roles.slice(0, 3)
          const remaining = roles.length - 3
          return (
            <div className="flex flex-wrap gap-1">
              {displayItems.map((role) => (
                <Badge key={role} variant="secondary" className="text-xs">
                  {role}
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
    [onView, onEdit, onDelete]
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
            placeholder="Search features..."
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
                  No feature permissions found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-muted-foreground">
          {pagination.total} feature(s) total
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
