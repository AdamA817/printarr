import { Link } from 'react-router-dom'
import {
  useDashboardStats,
  useDashboardCalendar,
  useDashboardQueue,
  useDashboardStorage,
} from '@/hooks/useDashboard'

export function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useDashboardStats()
  const { data: calendar, isLoading: calendarLoading } = useDashboardCalendar(14)
  const { data: queue, isLoading: queueLoading } = useDashboardQueue()
  const { data: storage, isLoading: storageLoading } = useDashboardStorage()

  return (
    <div className="space-y-6">
      {/* Stats Cards Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Designs"
          value={stats?.designs.total}
          subLabel={stats?.designs.downloaded ? `${stats.designs.downloaded} downloaded` : undefined}
          isLoading={statsLoading}
          icon="🎨"
          linkTo="/designs"
        />
        <StatCard
          label="Channels"
          value={stats?.channels.total}
          subLabel={stats?.channels.enabled ? `${stats.channels.enabled} enabled` : undefined}
          isLoading={statsLoading}
          icon="📡"
          linkTo="/channels"
        />
        <StatCard
          label="Queue"
          value={(stats?.downloads.active ?? 0) + (stats?.downloads.queued ?? 0)}
          subLabel={stats?.downloads.active ? `${stats.downloads.active} active` : undefined}
          isLoading={statsLoading}
          icon="⬇️"
          linkTo="/activity"
        />
        <StatCard
          label="Today"
          value={stats?.downloads.today}
          subLabel={stats?.downloads.this_week ? `${stats.downloads.this_week} this week` : undefined}
          isLoading={statsLoading}
          icon="📊"
        />
      </div>

      {/* Main content grid: Calendar (left) + Queue (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Calendar View (60% width on large screens) */}
        <div className="lg:col-span-3 bg-bg-secondary rounded-lg p-4">
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            Recent Activity
          </h2>
          {calendarLoading ? (
            <CalendarSkeleton />
          ) : calendar ? (
            <CalendarView days={calendar.days} />
          ) : (
            <p className="text-text-secondary">No data available</p>
          )}
        </div>

        {/* Queue Summary (40% width on large screens) */}
        <div className="lg:col-span-2 bg-bg-secondary rounded-lg p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-primary">Queue</h2>
            <Link
              to="/activity"
              className="text-sm text-accent-primary hover:text-accent-primary/80"
            >
              View All
            </Link>
          </div>
          {queueLoading ? (
            <QueueSkeleton />
          ) : queue ? (
            <QueueSummary queue={queue} />
          ) : (
            <p className="text-text-secondary">No queue data</p>
          )}
        </div>
      </div>

      {/* Storage Bar */}
      <div className="bg-bg-secondary rounded-lg p-4">
        <h2 className="text-lg font-semibold text-text-primary mb-4">Storage</h2>
        {storageLoading ? (
          <StorageSkeleton />
        ) : storage ? (
          <StorageBar storage={storage} />
        ) : (
          <p className="text-text-secondary">Storage data unavailable</p>
        )}
      </div>
    </div>
  )
}

// Stats Card Component
interface StatCardProps {
  label: string
  value: number | undefined
  subLabel?: string
  isLoading: boolean
  icon: string
  linkTo?: string
}

function StatCard({ label, value, subLabel, isLoading, icon, linkTo }: StatCardProps) {
  const content = (
    <div className="bg-bg-secondary rounded-lg p-4 hover:bg-bg-tertiary transition-colors">
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <h3 className="text-text-secondary text-sm font-medium">{label}</h3>
          {isLoading ? (
            <div className="h-7 w-12 bg-bg-tertiary rounded animate-pulse mt-1" />
          ) : (
            <>
              <p className="text-2xl font-bold text-text-primary">{value ?? 0}</p>
              {subLabel && (
                <p className="text-xs text-text-muted">{subLabel}</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )

  if (linkTo) {
    return <Link to={linkTo}>{content}</Link>
  }
  return content
}

// Calendar View Component
interface CalendarViewProps {
  days: Array<{
    date: string
    count: number
    designs: Array<{ id: string; title: string; thumbnail_url: string | null }>
  }>
}

function CalendarView({ days }: CalendarViewProps) {
  if (days.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-text-secondary">No designs in the last 14 days</p>
      </div>
    )
  }

  // Group by week for display
  const reversedDays = [...days].reverse() // Most recent first

  return (
    <div className="space-y-2">
      {reversedDays.map((day) => {
        const date = new Date(day.date)
        const isToday = isSameDay(date, new Date())
        const dayName = isToday ? 'Today' : date.toLocaleDateString('en-US', { weekday: 'short' })
        const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

        return (
          <div
            key={day.date}
            className={`flex items-center gap-4 p-2 rounded ${
              isToday ? 'bg-accent-primary/10' : 'hover:bg-bg-tertiary'
            }`}
          >
            <div className="w-20 text-sm">
              <span className={`font-medium ${isToday ? 'text-accent-primary' : 'text-text-primary'}`}>
                {dayName}
              </span>
              <span className="text-text-muted ml-1">{dateStr}</span>
            </div>
            <div className="flex-1 flex items-center gap-2">
              {day.count > 0 ? (
                <>
                  <div className="flex -space-x-1">
                    {day.designs.slice(0, 5).map((design) => (
                      <Link
                        key={design.id}
                        to={`/designs/${design.id}`}
                        className="w-8 h-8 rounded-full bg-bg-tertiary border-2 border-bg-secondary flex items-center justify-center text-xs hover:z-10 hover:ring-2 hover:ring-accent-primary"
                        title={design.title}
                      >
                        {design.thumbnail_url ? (
                          <img
                            src={design.thumbnail_url}
                            alt=""
                            className="w-full h-full object-cover rounded-full"
                          />
                        ) : (
                          '🎨'
                        )}
                      </Link>
                    ))}
                  </div>
                  {day.count > 5 && (
                    <span className="text-sm text-text-muted">+{day.count - 5} more</span>
                  )}
                </>
              ) : (
                <span className="text-sm text-text-muted">No designs</span>
              )}
            </div>
            <div className="text-sm font-medium text-text-primary">{day.count}</div>
          </div>
        )
      })}
    </div>
  )
}

function isSameDay(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  )
}

// Queue Summary Component
interface QueueSummaryProps {
  queue: {
    running: number
    queued: number
    recent_completions: Array<{
      id: string
      design_title: string | null
      finished_at: string | null
    }>
    recent_failures: Array<{
      id: string
      design_title: string | null
      error: string | null
    }>
  }
}

function QueueSummary({ queue }: QueueSummaryProps) {
  const hasActivity = queue.running > 0 || queue.queued > 0 ||
    queue.recent_completions.length > 0 || queue.recent_failures.length > 0

  if (!hasActivity) {
    return (
      <div className="text-center py-8">
        <p className="text-4xl mb-2">✨</p>
        <p className="text-text-secondary">Queue is empty</p>
        <p className="text-text-muted text-sm">No active or pending downloads</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Active/Queued counts */}
      {(queue.running > 0 || queue.queued > 0) && (
        <div className="flex gap-4">
          {queue.running > 0 && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-accent-primary animate-pulse" />
              <span className="text-sm text-text-primary">
                {queue.running} downloading
              </span>
            </div>
          )}
          {queue.queued > 0 && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-text-muted" />
              <span className="text-sm text-text-secondary">
                {queue.queued} queued
              </span>
            </div>
          )}
        </div>
      )}

      {/* Recent completions */}
      {queue.recent_completions.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-text-secondary mb-2">
            Recently Completed
          </h3>
          <div className="space-y-1">
            {queue.recent_completions.slice(0, 5).map((job) => (
              <div
                key={job.id}
                className="flex items-center gap-2 text-sm text-text-primary"
              >
                <span className="text-accent-success">✓</span>
                <span className="truncate">{job.design_title || 'Unknown'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent failures */}
      {queue.recent_failures.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-text-secondary mb-2">
            Recent Failures
          </h3>
          <div className="space-y-1">
            {queue.recent_failures.slice(0, 3).map((job) => (
              <div
                key={job.id}
                className="flex items-center gap-2 text-sm text-accent-danger"
                title={job.error || undefined}
              >
                <span>✗</span>
                <span className="truncate">{job.design_title || 'Unknown'}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Storage Bar Component
interface StorageBarProps {
  storage: {
    library_size_bytes: number
    staging_size_bytes: number
    cache_size_bytes: number
    available_bytes: number
    total_bytes: number
  }
}

function StorageBar({ storage }: StorageBarProps) {
  const used = storage.library_size_bytes + storage.staging_size_bytes + storage.cache_size_bytes
  const total = storage.total_bytes || 1 // Avoid division by zero

  const libraryPercent = (storage.library_size_bytes / total) * 100
  const stagingPercent = (storage.staging_size_bytes / total) * 100
  const cachePercent = (storage.cache_size_bytes / total) * 100
  const usedPercent = (used / total) * 100

  return (
    <div className="space-y-3">
      {/* Storage bar */}
      <div className="h-4 bg-bg-tertiary rounded-full overflow-hidden flex">
        <div
          className="bg-accent-success"
          style={{ width: `${libraryPercent}%` }}
          title={`Library: ${formatBytes(storage.library_size_bytes)}`}
        />
        <div
          className="bg-accent-warning"
          style={{ width: `${stagingPercent}%` }}
          title={`Staging: ${formatBytes(storage.staging_size_bytes)}`}
        />
        <div
          className="bg-accent-primary"
          style={{ width: `${cachePercent}%` }}
          title={`Cache: ${formatBytes(storage.cache_size_bytes)}`}
        />
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-accent-success" />
          <span className="text-text-secondary">
            Library: {formatBytes(storage.library_size_bytes)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-accent-warning" />
          <span className="text-text-secondary">
            Staging: {formatBytes(storage.staging_size_bytes)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-accent-primary" />
          <span className="text-text-secondary">
            Cache: {formatBytes(storage.cache_size_bytes)}
          </span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-text-primary font-medium">
            {formatBytes(storage.available_bytes)} free
          </span>
          <span className="text-text-muted">
            / {formatBytes(storage.total_bytes)} total ({usedPercent.toFixed(1)}% used)
          </span>
        </div>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

// Skeleton components
function CalendarSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="flex items-center gap-4 p-2">
          <div className="w-20 h-4 bg-bg-tertiary rounded animate-pulse" />
          <div className="flex-1 h-8 bg-bg-tertiary rounded animate-pulse" />
          <div className="w-8 h-4 bg-bg-tertiary rounded animate-pulse" />
        </div>
      ))}
    </div>
  )
}

function QueueSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <div className="h-4 w-24 bg-bg-tertiary rounded animate-pulse" />
        <div className="h-4 w-20 bg-bg-tertiary rounded animate-pulse" />
      </div>
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-5 bg-bg-tertiary rounded animate-pulse" />
        ))}
      </div>
    </div>
  )
}

function StorageSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-4 bg-bg-tertiary rounded-full animate-pulse" />
      <div className="flex gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-4 w-24 bg-bg-tertiary rounded animate-pulse" />
        ))}
      </div>
    </div>
  )
}
