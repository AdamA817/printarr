/**
 * Skeleton loader for ImportSourceCard
 */
export function ImportSourceCardSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-4 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        {/* Left side - icon and info */}
        <div className="flex items-start gap-4 flex-1">
          <div className="w-10 h-10 rounded-lg bg-bg-tertiary" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <div className="h-5 w-32 bg-bg-tertiary rounded" />
              <div className="h-4 w-20 bg-bg-tertiary rounded" />
            </div>
            <div className="h-4 w-64 bg-bg-tertiary rounded mt-2" />
            <div className="flex items-center gap-4 mt-2">
              <div className="h-3 w-24 bg-bg-tertiary rounded" />
              <div className="h-3 w-32 bg-bg-tertiary rounded" />
            </div>
          </div>
        </div>

        {/* Right side - actions */}
        <div className="flex items-center gap-3">
          <div className="h-6 w-16 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
        </div>
      </div>
    </div>
  )
}
