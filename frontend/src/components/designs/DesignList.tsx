import { useNavigate } from 'react-router-dom'
import { StatusBadge } from './StatusBadge'
import type { DesignListItem } from '@/types/design'

interface DesignListProps {
  designs: DesignListItem[]
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function DesignList({ designs }: DesignListProps) {
  const navigate = useNavigate()

  const handleRowClick = (id: string) => {
    navigate(`/designs/${id}`)
  }

  return (
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
            {designs.map((design) => (
              <tr
                key={design.id}
                onClick={() => handleRowClick(design.id)}
                className="hover:bg-bg-tertiary/50 transition-colors cursor-pointer"
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
    </div>
  )
}

// Skeleton loader for list
export function DesignListSkeleton() {
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
