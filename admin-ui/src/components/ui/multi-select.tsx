import * as React from 'react'
import { X, Check, ChevronsUpDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

interface MultiSelectProps {
  options: string[]
  selected: string[]
  onChange: (selected: string[]) => void
  placeholder?: string
  className?: string
  emptyMessage?: string
}

export function MultiSelect({
  options,
  selected,
  onChange,
  placeholder = 'Select items...',
  className,
  emptyMessage = 'No options available',
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  const [searchValue, setSearchValue] = React.useState('')

  const filteredOptions = React.useMemo(() => {
    if (!searchValue) return options
    return options.filter((option) =>
      option.toLowerCase().includes(searchValue.toLowerCase())
    )
  }, [options, searchValue])

  const handleSelect = (option: string) => {
    if (selected.includes(option)) {
      onChange(selected.filter((s) => s !== option))
    } else {
      onChange([...selected, option])
    }
  }

  const handleRemove = (option: string, e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(selected.filter((s) => s !== option))
  }

  const handleClearAll = (e: React.MouseEvent) => {
    e.stopPropagation()
    onChange([])
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'min-w-[200px] justify-between font-normal',
            selected.length === 0 && 'text-muted-foreground',
            className
          )}
        >
          <div className="flex flex-wrap gap-1 items-center max-w-[calc(100%-24px)] overflow-hidden">
            {selected.length === 0 ? (
              <span>{placeholder}</span>
            ) : selected.length <= 2 ? (
              selected.map((item) => (
                <Badge
                  key={item}
                  variant="secondary"
                  className="text-xs px-1.5 py-0"
                >
                  {item}
                  <button
                    type="button"
                    className="ml-1 hover:text-destructive"
                    onClick={(e) => handleRemove(item, e)}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))
            ) : (
              <>
                <Badge variant="secondary" className="text-xs px-1.5 py-0">
                  {selected[0]}
                  <button
                    type="button"
                    className="ml-1 hover:text-destructive"
                    onClick={(e) => handleRemove(selected[0], e)}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
                <Badge variant="outline" className="text-xs px-1.5 py-0">
                  +{selected.length - 1} more
                </Badge>
              </>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {selected.length > 0 && (
              <button
                type="button"
                className="hover:text-destructive"
                onClick={handleClearAll}
              >
                <X className="h-4 w-4" />
              </button>
            )}
            <ChevronsUpDown className="h-4 w-4 opacity-50" />
          </div>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[200px] p-0" align="start">
        <div className="p-2 border-b">
          <input
            type="text"
            placeholder="Search..."
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            className="w-full px-2 py-1.5 text-sm border rounded-md outline-none focus:ring-1 focus:ring-ring bg-transparent"
          />
        </div>
        <div className="max-h-[200px] overflow-y-auto p-1">
          {filteredOptions.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </div>
          ) : (
            filteredOptions.map((option) => {
              const isSelected = selected.includes(option)
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => handleSelect(option)}
                  className={cn(
                    'w-full flex items-center gap-2 px-2 py-1.5 text-sm rounded-md cursor-pointer hover:bg-accent',
                    isSelected && 'bg-accent'
                  )}
                >
                  <div
                    className={cn(
                      'flex h-4 w-4 items-center justify-center rounded border',
                      isSelected
                        ? 'bg-primary border-primary text-primary-foreground'
                        : 'border-muted-foreground/50'
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                  </div>
                  <span className="truncate">{option}</span>
                </button>
              )
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
