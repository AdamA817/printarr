import { useStats } from '@/hooks/useStats'

export function Dashboard() {
  const { data: stats, isLoading, error } = useStats()

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard
          label="Channels"
          value={stats?.channels_count}
          isLoading={isLoading}
          error={error}
        />
        <StatCard
          label="Designs"
          value={stats?.designs_count}
          isLoading={isLoading}
          error={error}
        />
        <StatCard
          label="Downloads"
          value={stats?.downloads_active}
          isLoading={isLoading}
          error={error}
        />
      </div>

      <div className="bg-bg-secondary rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Welcome to Printarr
        </h3>
        <p className="text-text-secondary">
          Monitor Telegram channels for 3D-printable designs, catalog them, and
          manage downloads into your structured local library.
        </p>
        <p className="text-text-muted mt-4 text-sm">
          Get started by adding a channel in the Channels section.
        </p>
      </div>
    </div>
  )
}

interface StatCardProps {
  label: string
  value: number | undefined
  isLoading: boolean
  error: Error | null
}

function StatCard({ label, value, isLoading, error }: StatCardProps) {
  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <h3 className="text-text-secondary text-sm font-medium">{label}</h3>
      {isLoading ? (
        <div className="h-9 w-16 bg-bg-tertiary rounded animate-pulse mt-2" />
      ) : error ? (
        <p className="text-accent-danger text-sm mt-2">Failed to load</p>
      ) : (
        <p className="text-3xl font-bold text-text-primary mt-2">
          {value ?? 0}
        </p>
      )}
    </div>
  )
}
