import { ChartColumn, Gavel, Wifi, WifiOff } from 'lucide-react'
import type { ReactNode } from 'react'
import { NavLink, Outlet } from 'react-router'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { type LiveState, useLiveUpdates } from '../hooks/useLiveUpdates'
import { cn } from '../lib/cn'
import { initials } from '../lib/format'
import { Skeleton } from './ui/Feedback'

export function Layout() {
  const live = useLiveUpdates()
  const { user } = useCurrentUser()

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:gap-6 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2.5 font-semibold text-slate-900">
            <span className="flex size-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-sm">
              <Gavel className="size-4.5" aria-hidden="true" />
            </span>
            <span className="hidden leading-tight sm:block">
              British Auction
              <span className="block text-xs font-normal text-slate-500">RFQ bidding</span>
            </span>
          </NavLink>

          <nav className="flex items-center gap-1 text-sm font-medium" aria-label="Main">
            <NavItem to="/" end>
              Auctions
            </NavItem>
            {user?.role === 'BUYER' && (
              <NavItem to="/metrics">
                <ChartColumn className="size-4" aria-hidden="true" />
                Metrics
              </NavItem>
            )}
          </nav>

          <div className="ml-auto flex items-center gap-2 sm:gap-4">
            <LiveIndicator state={live} />
            <UserSwitcher />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}

function NavItem({ to, end, children }: { to: string; end?: boolean; children: ReactNode }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-1.5 rounded-md px-3 py-2 transition-colors',
          isActive ? 'bg-slate-100 text-slate-900' : 'text-slate-600 hover:text-slate-900',
        )
      }
    >
      {children}
    </NavLink>
  )
}

const LIVE_META: Record<LiveState, { label: string; dot: string; title: string }> = {
  live: { label: 'Live', dot: 'bg-emerald-500', title: 'Receiving live updates' },
  connecting: { label: 'Connecting', dot: 'bg-amber-400', title: 'Connecting to live updates' },
  offline: {
    label: 'Offline',
    dot: 'bg-slate-400',
    title: 'Live updates paused; retrying. Pages still refresh every 30 seconds.',
  },
}

function LiveIndicator({ state }: { state: LiveState }) {
  const meta = LIVE_META[state]
  const Icon = state === 'offline' ? WifiOff : Wifi
  return (
    <span className="flex items-center gap-1.5 text-xs font-medium text-slate-600" title={meta.title}>
      <span className="relative flex size-2">
        {state === 'live' && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
        )}
        <span className={cn('relative inline-flex size-2 rounded-full', meta.dot)} />
      </span>
      <Icon className="size-3.5 sm:hidden" aria-hidden="true" />
      <span className="hidden sm:inline">{meta.label}</span>
    </span>
  )
}

function UserSwitcher() {
  const { users, user, isLoading, switchUser } = useCurrentUser()
  if (isLoading || !user) return <Skeleton className="h-9 w-44" />

  const buyers = users.filter((u) => u.role === 'BUYER')
  const suppliers = users.filter((u) => u.role === 'SUPPLIER')
  return (
    <label className="flex items-center gap-2">
      <span
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
          user.role === 'BUYER' ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700',
        )}
        aria-hidden="true"
      >
        {initials(user.company)}
      </span>
      <span className="sr-only">Acting as</span>
      <select
        value={user.id}
        onChange={(event) => switchUser(event.target.value)}
        className="max-w-[11rem] truncate rounded-lg border-0 bg-white py-1.5 pr-8 pl-2.5 text-sm font-medium text-slate-900 ring-1 ring-slate-300 ring-inset focus:ring-2 focus:ring-blue-600 focus:outline-none sm:max-w-[16rem]"
        title="Switch between the buyer and supplier views"
      >
        <optgroup label="Buyer">
          {buyers.map((u) => (
            <option key={u.id} value={u.id}>
              {u.company} · {u.name}
            </option>
          ))}
        </optgroup>
        <optgroup label="Suppliers">
          {suppliers.map((u) => (
            <option key={u.id} value={u.id}>
              {u.company} · {u.name}
            </option>
          ))}
        </optgroup>
      </select>
    </label>
  )
}
