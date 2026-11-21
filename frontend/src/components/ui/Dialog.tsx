import { type ReactNode, useEffect, useId, useRef } from 'react'
import { X } from 'lucide-react'

interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  footer?: ReactNode
}

export function Dialog({ open, onClose, title, description, children, footer }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose() // click on the backdrop
      }}
      className="w-[min(calc(100vw-2rem),34rem)] rounded-2xl bg-white p-0 text-slate-900 shadow-2xl"
    >
      <div className="flex items-start justify-between gap-4 px-6 pt-5">
        <div>
          <h2 id={titleId} className="text-base font-semibold">
            {title}
          </h2>
          {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="-mr-2 rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          aria-label="Close"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="px-6 py-4">{children}</div>
      {footer && (
        <div className="flex flex-wrap justify-end gap-2 rounded-b-2xl border-t border-slate-100 bg-slate-50 px-6 py-3">
          {footer}
        </div>
      )}
    </dialog>
  )
}
