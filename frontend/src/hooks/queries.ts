import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { BidPayload, DemoPayload, RfqCreatePayload } from '../lib/types'
import { useCurrentUser } from './useCurrentUser'

// buyer and supplier views differ, so keys include the user
export const queryKeys = {
  rfqs: (userId: string) => ['rfqs', userId] as const,
  rfq: (rfqId: string, userId: string) => ['rfq', rfqId, userId] as const,
  metrics: (userId: string) => ['metrics', userId] as const,
}

// fallback in case the websocket drops
const SAFETY_POLL_MS = 30_000

function useUserId(): string {
  return useCurrentUser().user?.id ?? ''
}

export function useRfqs() {
  const userId = useUserId()
  return useQuery({
    queryKey: queryKeys.rfqs(userId),
    queryFn: () => api.listRfqs(userId),
    enabled: userId !== '',
    placeholderData: keepPreviousData,
    refetchInterval: SAFETY_POLL_MS,
  })
}

export function useRfq(rfqId: string) {
  const userId = useUserId()
  return useQuery({
    queryKey: queryKeys.rfq(rfqId, userId),
    queryFn: () => api.getRfq(userId, rfqId),
    enabled: userId !== '' && rfqId !== '',
    placeholderData: keepPreviousData,
    refetchInterval: SAFETY_POLL_MS,
  })
}

export function useMetrics(enabled: boolean) {
  const userId = useUserId()
  return useQuery({
    queryKey: queryKeys.metrics(userId),
    queryFn: () => api.metrics(userId),
    enabled: enabled && userId !== '',
    placeholderData: keepPreviousData,
  })
}

export function useCreateRfq() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: RfqCreatePayload) => api.createRfq(userId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rfqs'] }),
  })
}

export function usePlaceBid(rfqId: string) {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: BidPayload) => api.placeBid(userId, rfqId, payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['rfq', rfqId] }),
        queryClient.invalidateQueries({ queryKey: ['rfqs'] }),
      ])
    },
  })
}

export function useAward(rfqId: string) {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (bidId: string) => api.award(userId, rfqId, bidId),
    onSuccess: (detail) => {
      queryClient.setQueryData(queryKeys.rfq(rfqId, userId), detail)
      void queryClient.invalidateQueries({ queryKey: ['rfqs'] })
    },
  })
}

export function useLaunchDemo() {
  const userId = useUserId()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: DemoPayload) => api.launchDemo(userId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rfqs'] }),
  })
}
