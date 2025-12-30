import type { DesignListParams } from '@/types/design'

interface ActiveFiltersProps {
  filters: DesignListParams
  channelName?: string
  onRemove: (key: keyof DesignListParams) => void
}

export function ActiveFilters({ filters, channelName, onRemove }: ActiveFiltersProps) {
  const pills: { key: keyof DesignListParams; label: string }[] = []

  if (filters.status) {
    pills.push({ key: 'status', label: `Status: ${filters.status}` })
  }

  if (filters.channel_id && channelName) {
    pills.push({ key: 'channel_id', label: `Channel: ${channelName}` })
  }

  if (filters.file_type) {
    pills.push({ key: 'file_type', label: `Type: ${filters.file_type}` })
  }

  if (filters.multicolor) {
    const label = filters.multicolor === 'MULTI' ? 'Multicolor' :
      filters.multicolor === 'SINGLE' ? 'Single Color' : 'Unknown Color'
    pills.push({ key: 'multicolor', label })
  }

  if (filters.has_thangs_link !== undefined) {
    pills.push({
      key: 'has_thangs_link',
      label: filters.has_thangs_link ? 'Thangs: Linked' : 'Thangs: Not Linked',
    })
  }

  if (filters.q) {
    pills.push({ key: 'q', label: `Search: "${filters.q}"` })
  }

  if (filters.designer) {
    pills.push({ key: 'designer', label: `Designer: ${filters.designer}` })
  }

  if (pills.length === 0) return null

  return (
    <div className="flex flex-wrap gap-2">
      {pills.map(({ key, label }) => (
        <FilterPill key={key} label={label} onRemove={() => onRemove(key)} />
      ))}
    </div>
  )
}

function FilterPill({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-bg-tertiary rounded text-sm text-text-secondary">
      {label}
      <button
        onClick={onRemove}
        className="hover:text-text-primary transition-colors"
        aria-label={`Remove ${label} filter`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </span>
  )
}
