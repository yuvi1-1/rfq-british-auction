import type { ComponentProps, ReactNode } from 'react'
import { cn } from '../../lib/cn'

interface FieldProps {
  label: ReactNode
  htmlFor: string
  error?: string
  hint?: ReactNode
  required?: boolean
  className?: string
  children: ReactNode
}

export function Field({ label, htmlFor, error, hint, required, className, children }: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">
        {label}
        {required && (
          <span className="text-red-500" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : (
        hint && (
          <p id={`${htmlFor}-hint`} className="text-xs text-slate-500">
            {hint}
          </p>
        )
      )}
    </div>
  )
}

const control =
  'block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ring-1 ring-slate-300 ring-inset ' +
  'placeholder:text-slate-400 focus:ring-2 focus:ring-blue-600 focus:outline-none focus:ring-inset ' +
  'disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 aria-[invalid=true]:ring-red-500'

export function Input({ className, ...props }: ComponentProps<'input'>) {
  return <input className={cn(control, className)} {...props} />
}

export function Select({ className, ...props }: ComponentProps<'select'>) {
  return <select className={cn(control, 'pr-8', className)} {...props} />
}

const CURRENCY_SYMBOLS: Record<string, string> = { USD: '$', EUR: '€', INR: '₹' }

export function MoneyInput({
  currency,
  className,
  ...props
}: ComponentProps<'input'> & { currency: string }) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-sm text-slate-500">
        {CURRENCY_SYMBOLS[currency] ?? currency}
      </span>
      <Input
        type="number"
        inputMode="decimal"
        min="0"
        step="0.01"
        className={cn('pl-7', className)}
        {...props}
      />
    </div>
  )
}
