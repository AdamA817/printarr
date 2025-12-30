import { useQueue, useQueueStats } from '@/hooks/useQueue'
import { QueueItem } from './QueueItem'

export function QueueView() {
  const { data: queueData, isLoading, error } = useQueue()
  const { data: stats } = useQueueStats()

  if (isLoading) {
    return <QueueViewSkeleton />
  }

  if (error) {
    return (
      <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
        <p className="text-accent-danger">
          Failed to load queue: {(error as Error).message}
        </p>
      </div>
    )
  }

  const items = queueData?.items || []
  const activeItems = items.filter(item => item.status === 'RUNNING')
  const queuedItems = items.filter(item => item.status === 'QUEUED')

  const isEmpty = items.length === 0

  return (
    <div className="space-y-6">
      {/* Stats summary */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            label="Downloading"
            value={stats.downloading}
            color="text-accent-primary"
          />
          <StatCard
            label="Extracting"
            value={stats.extracting}
            color="text-accent-warning"
          />
          <StatCard
            label="Importing"
            value={stats.importing}
            color="text-accent-success"
          />
          <StatCard
            label="In Queue"
            value={stats.queued}
            color="text-text-secondary"
          />
        </div>
      )}

      {/* Empty state */}
      {isEmpty && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <EmptyQueueIcon className="w-16 h-16 mx-auto text-text-muted mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">
            Queue is empty
          </h3>
          <p className="text-text-secondary">
            Mark designs as "Wanted" to add them to the download queue.
          </p>
        </div>
      )}

      {/* Active downloads */}
      {activeItems.length > 0 && (
        <section>
          <h2 className="text-lg font-medium text-text-primary mb-3 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-primary animate-pulse" />
            Currently Active ({activeItems.length})
          </h2>
          <div className="space-y-3">
            {activeItems.map((item) => (
              <QueueItem key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}

      {/* Queued items */}
      {queuedItems.length > 0 && (
        <section>
          <h2 className="text-lg font-medium text-text-primary mb-3">
            Waiting ({queuedItems.length})
          </h2>
          <div className="space-y-3">
            {queuedItems.map((item, index) => (
              <QueueItem key={item.id} item={item} position={index + 1} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

// Stats card component
function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-bg-secondary rounded-lg p-4">
      <p className="text-text-muted text-sm">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  )
}

// Empty queue icon
function EmptyQueueIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="9" y1="9" x2="15" y2="9" />
      <line x1="9" y1="13" x2="15" y2="13" />
      <line x1="9" y1="17" x2="12" y2="17" />
    </svg>
  )
}

// Skeleton loader
function QueueViewSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Stats skeleton */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-bg-secondary rounded-lg p-4">
            <div className="h-4 bg-bg-tertiary rounded w-16 mb-2" />
            <div className="h-8 bg-bg-tertiary rounded w-8" />
          </div>
        ))}
      </div>

      {/* Items skeleton */}
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-bg-secondary rounded-lg p-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-bg-tertiary rounded-lg" />
              <div className="flex-1 space-y-2">
                <div className="h-5 bg-bg-tertiary rounded w-2/3" />
                <div className="h-4 bg-bg-tertiary rounded w-1/2" />
                <div className="h-2 bg-bg-tertiary rounded w-full mt-3" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
