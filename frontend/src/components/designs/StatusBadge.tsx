import type { DesignStatus } from '@/types/design'

// Status badge colors matching Radarr style
const statusColors: Record<DesignStatus, string> = {
  DISCOVERED: 'bg-text-muted text-text-primary',
  WANTED: 'bg-accent-primary text-white',
  DOWNLOADING: 'bg-accent-warning text-white',
  DOWNLOADED: 'bg-accent-success text-white',
  EXTRACTING: 'bg-accent-warning text-white',
  EXTRACTED: 'bg-accent-success text-white',
  IMPORTING: 'bg-accent-warning text-white',
  ORGANIZED: 'bg-accent-success text-white',
  FAILED: 'bg-accent-danger text-white',
}

const statusLabels: Record<DesignStatus, string> = {
  DISCOVERED: 'Discovered',
  WANTED: 'Wanted',
  DOWNLOADING: 'Downloading',
  DOWNLOADED: 'Downloaded',
  EXTRACTING: 'Extracting',
  EXTRACTED: 'Extracted',
  IMPORTING: 'Importing',
  ORGANIZED: 'Organized',
  FAILED: 'Failed',
}

interface StatusBadgeProps {
  status: DesignStatus
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs'

  return (
    <span
      className={`rounded font-medium ${statusColors[status]} ${sizeClasses}`}
    >
      {statusLabels[status]}
    </span>
  )
}
