import { useQuery } from '@tanstack/react-query'
import { type ReactNode, useCallback, useMemo, useState } from 'react'
import { CurrentUserContext } from '../hooks/useCurrentUser'
import { api } from '../lib/api'

const STORAGE_KEY = 'rfq-auction:acting-user'

function readStoredUserId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

function storeUserId(userId: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, userId)
  } catch {
    // ignore (e.g. private mode)
  }
}

export function CurrentUserProvider({ children }: { children: ReactNode }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['users'],
    queryFn: api.users,
    staleTime: 5 * 60_000,
  })
  const [selectedId, setSelectedId] = useState<string | null>(readStoredUserId)

  const users = useMemo(() => data ?? [], [data])
  const user =
    users.find((u) => u.id === selectedId) ?? users.find((u) => u.role === 'BUYER') ?? null

  const switchUser = useCallback((userId: string) => {
    storeUserId(userId)
    setSelectedId(userId)
  }, [])

  const value = useMemo(
    () => ({ users, user, isLoading, error, switchUser }),
    [users, user, isLoading, error, switchUser],
  )
  return <CurrentUserContext value={value}>{children}</CurrentUserContext>
}
