import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { Skeleton } from './components/ui/Feedback'
import { AuctionsPage } from './pages/AuctionsPage'
import { NotFoundPage } from './pages/NotFoundPage'

// lazy-load the bigger pages
const AuctionDetailPage = lazy(() =>
  import('./pages/auction/AuctionDetailPage').then((m) => ({ default: m.AuctionDetailPage })),
)
const CreateRfqPage = lazy(() =>
  import('./pages/CreateRfqPage').then((m) => ({ default: m.CreateRfqPage })),
)
const MetricsPage = lazy(() => import('./pages/MetricsPage').then((m) => ({ default: m.MetricsPage })))

function PageFallback() {
  return (
    <div className="space-y-4" aria-busy="true">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-40 w-full" />
    </div>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<AuctionsPage />} />
        <Route
          path="rfqs/new"
          element={
            <Suspense fallback={<PageFallback />}>
              <CreateRfqPage />
            </Suspense>
          }
        />
        <Route
          path="rfqs/:rfqId"
          element={
            <Suspense fallback={<PageFallback />}>
              <AuctionDetailPage />
            </Suspense>
          }
        />
        <Route
          path="metrics"
          element={
            <Suspense fallback={<PageFallback />}>
              <MetricsPage />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
