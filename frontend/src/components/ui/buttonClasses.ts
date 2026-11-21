import { cn } from '../../lib/cn'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'success'
export type ButtonSize = 'sm' | 'md'

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-blue-600 text-white shadow-sm hover:bg-blue-700 focus-visible:outline-blue-600 disabled:bg-blue-300',
  secondary:
    'bg-white text-slate-700 shadow-sm ring-1 ring-slate-300 ring-inset hover:bg-slate-50 focus-visible:outline-blue-600 disabled:text-slate-400',
  ghost: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-blue-600',
  success:
    'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 focus-visible:outline-emerald-600 disabled:bg-emerald-300',
}

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 gap-1.5 px-3 text-sm',
  md: 'h-10 gap-2 px-4 text-sm',
}

export function buttonClasses(
  variant: ButtonVariant = 'primary',
  size: ButtonSize = 'md',
  className?: string,
): string {
  return cn(
    'inline-flex shrink-0 items-center justify-center rounded-lg font-medium whitespace-nowrap transition-colors',
    'focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed',
    VARIANTS[variant],
    SIZES[size],
    className,
  )
}
