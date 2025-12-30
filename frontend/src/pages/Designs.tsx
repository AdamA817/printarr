import { useState } from 'react'
import { useDesigns } from '@/hooks/useDesigns'
import type { DesignListParams, DesignStatus } from '@/types/design'

// Status badge colors matching Radarr style
const statusColors: Record<DesignStatus, string> = {
  DISCOVERED: 'bg-text-muted text-text-primary',
  WANTED: 'bg-accent-primary text-white',
  DOWNLOADING: 'bg-accent-warning text-white',
  DOWNLOADED: 'bg-accent-success text-white',
  ORGANIZED: 'bg-accent-success text-white',
}

const statusLabels: Record<DesignStatus, string> = {
  DISCOVERED: 'Discovered',
  WANTED: 'Wanted',
  DOWNLOADING: 'Downloading',
  DOWNLOADED: 'Downloaded',
  ORGANIZED: 'Organized',
}

function StatusBadge({ status }: { status: DesignStatus }) {
  return (
    <span
      className={`px-2 py-1 rounded text-xs font-medium ${statusColors[status]}`}
    >
      {statusLabels[status]}
    </span>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function DesignsTableSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="bg-bg-secondary rounded-lg overflow-hidden">
        <div className="h-12 bg-bg-tertiary" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-16 border-t border-bg-tertiary">
            <div className="flex items-center h-full px-4 gap-4">
              <div className="h-4 bg-bg-tertiary rounded w-1/4" />
              <div className="h-4 bg-bg-tertiary rounded w-1/6" />
              <div className="h-4 bg-bg-tertiary rounded w-1/6" />
              <div className="h-6 bg-bg-tertiary rounded w-20" />
              <div className="h-4 bg-bg-tertiary rounded w-16" />
              <div className="h-4 bg-bg-tertiary rounded w-8" />
              <div className="h-4 bg-bg-tertiary rounded w-24" />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Designs() {
  const [params, setParams] = useState<DesignListParams>({
    page: 1,
    page_size: 20,
  })

  const { data, isLoading, error } = useDesigns(params)

  const handlePageChange = (newPage: number) => {
    setParams((prev) => ({ ...prev, page: newPage }))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Designs</h1>
          {data && (
            <p className="text-sm text-text-secondary mt-1">
              {data.total} design{data.total !== 1 ? 's' : ''}
            </p>
          )}
        </div>
      </div>

      {/* Loading state */}
      {isLoading && <DesignsTableSkeleton />}

      {/* Error state */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load designs: {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <div className="text-4xl mb-4">🎨</div>
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No designs yet
          </h3>
          <p className="text-text-secondary mb-4">
            Designs will appear here after you run a backfill on a channel with 3D models.
          </p>
        </div>
      )}

      {/* Table */}
      {data && data.items.length > 0 && (
        <div className="bg-bg-secondary rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-bg-tertiary text-left text-sm text-text-secondary">
                  <th className="px-4 py-3 font-medium">Title</th>
                  <th className="px-4 py-3 font-medium">Designer</th>
                  <th className="px-4 py-3 font-medium">Channel</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">File Types</th>
                  <th className="px-4 py-3 font-medium">Thangs</th>
                  <th className="px-4 py-3 font-medium">Added</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-bg-tertiary">
                {data.items.map((design) => (
                  <tr
                    key={design.id}
                    className="hover:bg-bg-tertiary/50 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <span className="text-text-primary font-medium truncate block max-w-xs">
                        {design.canonical_title}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {design.canonical_designer}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {design.channel?.title || '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={design.status} />
                    </td>
                    <td className="px-4 py-3 text-text-secondary text-sm">
                      {design.file_types.length > 0
                        ? design.file_types.join(', ')
                        : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {design.has_thangs_link ? (
                        <span
                          className="text-accent-primary"
                          title="Linked to Thangs"
                        >
                          🔗
                        </span>
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-text-secondary text-sm">
                      {formatDate(design.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="px-4 py-3 border-t border-bg-tertiary flex items-center justify-between">
              <p className="text-sm text-text-secondary">
                Page {data.page} of {data.pages}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => handlePageChange(data.page - 1)}
                  disabled={data.page <= 1}
                  className="px-3 py-1 text-sm rounded bg-bg-tertiary text-text-secondary hover:bg-bg-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => handlePageChange(data.page + 1)}
                  disabled={data.page >= data.pages}
                  className="px-3 py-1 text-sm rounded bg-bg-tertiary text-text-secondary hover:bg-bg-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
