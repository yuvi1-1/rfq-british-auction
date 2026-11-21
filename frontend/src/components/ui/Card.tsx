import type { ComponentProps, ReactNode } from 'react'
import { cn } from '../../lib/cn'

export function Card({ className, ...props }: ComponentProps<'section'>) {
  return (
    <section
      className={cn('rounded-xl border border-slate-200 bg-white shadow-sm', className)}
      {...props}
    />
  )
}

interface CardHeaderProps {
  title: ReactNode
  description?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  className?: string
}

export function CardHeader({ title, description, icon, actions, className }: CardHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4',
        className,
      )}
    >
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          {icon && <span className="text-slate-400">{icon}</span>}
          {title}
        </h2>
        {description && <p className="mt-0.5 text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

export function CardBody({ className, ...props }: ComponentProps<'div'>) {
  return <div className={cn('px-5 py-4', className)} {...props} />
}
