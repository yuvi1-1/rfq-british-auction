import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { formatDuration, formatTime } from '../lib/format'
import { TRIGGER_META } from '../lib/status'
import type { LiveMessage } from '../lib/types'

export type LiveState = 'connecting' | 'live' | 'offline'

const PING_MS = 25_000
const MAX_RETRY_MS = 15_000

export function useLiveUpdates(): LiveState {
  const queryClient = useQueryClient()
  const [state, setState] = useState<LiveState>('connecting')

  useEffect(() => {
    let socket: WebSocket | null = null
    let attempt = 0
    let stopped = false
    let pingTimer: ReturnType<typeof setInterval> | undefined
    let retryTimer: ReturnType<typeof setTimeout> | undefined

    const handle = (message: LiveMessage) => {
      void queryClient.invalidateQueries({ queryKey: ['rfqs'] })
      void queryClient.invalidateQueries({ queryKey: ['rfq', message.rfq_id] })
      void queryClient.invalidateQueries({ queryKey: ['metrics'] })

      const extension = message.extension
      if (message.type === 'bid_placed' && extension?.extended) {
        const added = Date.parse(extension.new_close_at) - Date.parse(extension.old_close_at)
        toast.warning(`${message.reference_id} extended by ${formatDuration(added)}`, {
          id: `ext-${message.rfq_id}`,
          description: `${TRIGGER_META[extension.trigger].short} in the trigger window. Now closes at ${formatTime(extension.new_close_at)}${extension.capped ? ' (the forced close).' : '.'}`,
        })
      } else if (message.type === 'auction_closed') {
        const forced = Date.parse(message.current_close_at) >= Date.parse(message.forced_close_at)
        toast(`${message.reference_id} ${forced ? 'force-closed' : 'closed'}`, {
          id: `closed-${message.rfq_id}`,
          description: message.name,
        })
      }
    }

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/rfqs`)
      socket.onopen = () => {
        attempt = 0
        setState('live')
        // refetch anything missed while disconnected
        void queryClient.invalidateQueries({ queryKey: ['rfqs'] })
        void queryClient.invalidateQueries({ queryKey: ['rfq'] })
        pingTimer = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
        }, PING_MS)
      }
      socket.onmessage = (event: MessageEvent<string>) => {
        try {
          handle(JSON.parse(event.data) as LiveMessage)
        } catch {
          // ignore bad messages
        }
      }
      socket.onclose = () => {
        clearInterval(pingTimer)
        if (stopped) return
        setState('offline')
        retryTimer = setTimeout(connect, Math.min(1000 * 2 ** attempt++, MAX_RETRY_MS))
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    return () => {
      stopped = true
      clearInterval(pingTimer)
      clearTimeout(retryTimer)
      socket?.close()
    }
  }, [queryClient])

  return state
}
