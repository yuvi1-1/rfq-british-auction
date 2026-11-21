import { CircleExclamationPoint } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cn('animate-spin', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-slate-200/80', className)} />
}

interface EmptyStateProps {
  icon: ReactNode
  title: string
  description?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center px-6 py-12 text-center', className)}>
      <div className="flex size-11 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        {icon}
      </div>
      <h3 className="mt-3 text-sm font-semibold text-slate-900">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, retry }: { error: Error; retry?: () => void }) {
  return (
    <EmptyState
      icon={<CircleExclamationPoint className="size-5 text-red-500" />}
      title="Something went wrong"
      description={error.message}
      action={
        retry && (
          <button
            type="button"
            onClick={retry}
            className="text-sm font-medium text-blue-600 hover:text-blue-700"
          >
            Try again
          </button>
        )
      }
    />
  )
}
