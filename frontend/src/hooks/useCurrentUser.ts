import { createContext, use } from 'react'
import type { User } from '../lib/types'

export interface CurrentUserValue {
  users: User[]
  user: User | null
  isLoading: boolean
  error: Error | null
  switchUser: (userId: string) => void
}

export const CurrentUserContext = createContext<CurrentUserValue | null>(null)

export function useCurrentUser(): CurrentUserValue {
  const value = use(CurrentUserContext)
  if (!value) throw new Error('useCurrentUser must be used inside <CurrentUserProvider>')
  return value
}
