export function ChannelCardSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-4 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Avatar skeleton */}
          <div className="w-10 h-10 rounded-full bg-bg-tertiary" />
          <div className="space-y-2">
            {/* Title skeleton */}
            <div className="h-4 w-32 bg-bg-tertiary rounded" />
            {/* Username skeleton */}
            <div className="h-3 w-24 bg-bg-tertiary rounded" />
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Status badge skeleton */}
          <div className="h-6 w-16 bg-bg-tertiary rounded" />
          {/* Action buttons skeleton */}
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
          <div className="h-8 w-8 bg-bg-tertiary rounded" />
        </div>
      </div>
    </div>
  )
}
