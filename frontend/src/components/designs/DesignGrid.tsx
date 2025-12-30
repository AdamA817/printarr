import { DesignCard, DesignCardSkeleton } from './DesignCard'
import type { DesignListItem } from '@/types/design'

interface DesignGridProps {
  designs: DesignListItem[]
}

export function DesignGrid({ designs }: DesignGridProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {designs.map((design) => (
        <DesignCard key={design.id} design={design} />
      ))}
    </div>
  )
}

// Skeleton loader for grid
export function DesignGridSkeleton({ count = 12 }: { count?: number }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
      {[...Array(count)].map((_, i) => (
        <DesignCardSkeleton key={i} />
      ))}
    </div>
  )
}
