import { cn } from '../../lib/cn'

interface Option<T extends string> {
  value: T
  label: string
  count?: number
}

interface SegmentedProps<T extends string> {
  label: string
  value: T
  options: Option<T>[]
  onChange: (value: T) => void
  className?: string
}

export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
  className,
}: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className={cn('inline-flex max-w-full overflow-x-auto rounded-lg bg-slate-100 p-1', className)}
    >
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium whitespace-nowrap transition-colors',
              'focus-visible:outline-2 focus-visible:outline-blue-600',
              selected ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900',
            )}
          >
            {option.label}
            {option.count !== undefined && (
              <span
                className={cn(
                  'rounded-full px-1.5 text-xs tabular-nums',
                  selected ? 'bg-slate-100 text-slate-700' : 'text-slate-400',
                )}
              >
                {option.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
