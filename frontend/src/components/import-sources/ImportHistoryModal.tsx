/**
 * Modal for viewing import history of a source
 */
import { useNavigate } from 'react-router-dom'
import { ImportHistoryList } from './ImportHistoryList'
import type { ImportSource } from '@/types/import-source'

interface ImportHistoryModalProps {
  isOpen: boolean
  source: ImportSource | null
  onClose: () => void
}

export function ImportHistoryModal({ isOpen, source, onClose }: ImportHistoryModalProps) {
  const navigate = useNavigate()

  if (!isOpen || !source) return null

  const handleDesignClick = (designId: string) => {
    navigate(`/designs/${designId}`)
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Import History</h2>
            <p className="text-sm text-text-secondary mt-0.5">{source.name}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-text-muted hover:text-text-primary transition-colors"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Source stats */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <StatCard
              label="Imported"
              value={source.items_imported}
              color="text-accent-success"
            />
            <StatCard
              label="Last Sync"
              value={source.last_sync_at ? formatRelativeTime(source.last_sync_at) : 'Never'}
              color="text-text-primary"
            />
            <StatCard
              label="Status"
              value={formatStatus(source.status)}
              color={getStatusColor(source.status)}
            />
          </div>

          {/* History list */}
          <ImportHistoryList
            sourceId={source.id}
            onDesignClick={handleDesignClick}
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4 border-t border-bg-tertiary">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-bg-tertiary text-text-primary rounded-lg hover:bg-bg-tertiary/80 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// Sub-components
// =============================================================================

interface StatCardProps {
  label: string
  value: string | number
  color: string
}

function StatCard({ label, value, color }: StatCardProps) {
  return (
    <div className="bg-bg-tertiary rounded-lg p-3 text-center">
      <p className="text-xs text-text-muted uppercase tracking-wider">{label}</p>
      <p className={`text-lg font-semibold ${color} mt-1`}>{value}</p>
    </div>
  )
}

// =============================================================================
// Utilities
// =============================================================================

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function formatStatus(status: string): string {
  return status.charAt(0) + status.slice(1).toLowerCase()
}

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    ACTIVE: 'text-accent-success',
    PAUSED: 'text-text-muted',
    ERROR: 'text-accent-danger',
    PENDING: 'text-accent-warning',
  }
  return colors[status] || 'text-text-primary'
}

// =============================================================================
// Icons
// =============================================================================

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
