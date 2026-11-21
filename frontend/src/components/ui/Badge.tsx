import type { ComponentProps } from 'react'
import { cn } from '../../lib/cn'

const TONES = {
  neutral: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  blue: 'bg-blue-50 text-blue-700 ring-blue-600/20',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  amber: 'bg-amber-50 text-amber-800 ring-amber-600/25',
  violet: 'bg-violet-50 text-violet-700 ring-violet-600/20',
  gold: 'bg-amber-100 text-amber-900 ring-amber-500/40',
} as const

export type BadgeTone = keyof typeof TONES

interface BadgeProps extends ComponentProps<'span'> {
  tone?: BadgeTone
}

export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset',
        TONES[tone],
        className,
      )}
      {...props}
    />
  )
}
