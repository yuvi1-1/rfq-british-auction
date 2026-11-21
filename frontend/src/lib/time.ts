import { useSyncExternalStore } from 'react'

let offsetMs = 0

export function syncServerClock(serverTime: string | null): void {
  if (!serverTime) return
  const parsed = Date.parse(serverTime)
  if (!Number.isNaN(parsed)) offsetMs = parsed - Date.now()
}

export function serverNow(): number {
  return Date.now() + offsetMs
}

// one shared 1s timer for the whole app
const listeners = new Set<() => void>()
let current = serverNow()
let timer: ReturnType<typeof setInterval> | undefined

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  if (timer === undefined) {
    current = serverNow()
    timer = setInterval(() => {
      current = serverNow()
      for (const notify of listeners) notify()
    }, 1000)
  }
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0 && timer !== undefined) {
      clearInterval(timer)
      timer = undefined
    }
  }
}

const getSnapshot = () => current

export function useNow(): number {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

/** value for <input type="datetime-local"> */
export function toLocalInputValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  )
}

/** value for <input type="date"> */
export function toLocalDateValue(date: Date): string {
  return toLocalInputValue(date).slice(0, 10)
}
