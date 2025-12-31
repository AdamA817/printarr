import type { DownloadMode } from '@/types/channel'

interface DownloadModeBadgeProps {
  mode: DownloadMode
  size?: 'sm' | 'md'
}

const modeConfig: Record<DownloadMode, { label: string; icon: string; className: string }> = {
  MANUAL: {
    label: 'Manual',
    icon: '👆',
    className: 'bg-text-muted/20 text-text-secondary',
  },
  DOWNLOAD_ALL_NEW: {
    label: 'Auto-New',
    icon: '🆕',
    className: 'bg-accent-primary/20 text-accent-primary',
  },
  DOWNLOAD_ALL: {
    label: 'Auto-All',
    icon: '⚡',
    className: 'bg-accent-success/20 text-accent-success',
  },
}

export function DownloadModeBadge({ mode, size = 'sm' }: DownloadModeBadgeProps) {
  const config = modeConfig[mode]
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-sm'

  return (
    <span
      className={`inline-flex items-center gap-1 rounded font-medium ${config.className} ${sizeClasses}`}
      title={getTooltip(mode)}
    >
      <span aria-hidden="true">{config.icon}</span>
      <span>{config.label}</span>
    </span>
  )
}

function getTooltip(mode: DownloadMode): string {
  switch (mode) {
    case 'MANUAL':
      return 'Downloads require manual approval'
    case 'DOWNLOAD_ALL_NEW':
      return 'New designs are automatically downloaded'
    case 'DOWNLOAD_ALL':
      return 'All designs are automatically downloaded'
  }
}
