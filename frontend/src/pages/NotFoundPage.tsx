import { Compass } from 'lucide-react'
import { Link } from 'react-router'
import { buttonClasses } from '../components/ui/buttonClasses'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/Feedback'

export function NotFoundPage() {
  return (
    <Card className="mx-auto max-w-lg">
      <title>Not found · British Auction RFQ</title>
      <EmptyState
        icon={<Compass className="size-5" />}
        title="Page not found"
        description="The page you are looking for does not exist."
        action={<Link to="/" className={buttonClasses('secondary')}>Go to auctions</Link>}
      />
    </Card>
  )
}
