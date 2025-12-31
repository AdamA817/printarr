import { useChannels } from '@/hooks/useChannels'
import type { DesignListParams, DesignStatus, MulticolorStatus } from '@/types/design'

interface FilterSidebarProps {
  filters: DesignListParams
  onChange: (filters: DesignListParams) => void
  onClearAll: () => void
  isOpen: boolean
  onClose: () => void
}

const STATUSES: { value: DesignStatus; label: string }[] = [
  { value: 'DISCOVERED', label: 'Discovered' },
  { value: 'WANTED', label: 'Wanted' },
  { value: 'DOWNLOADING', label: 'Downloading' },
  { value: 'DOWNLOADED', label: 'Downloaded' },
  { value: 'ORGANIZED', label: 'Organized' },
  { value: 'FAILED', label: 'Failed' },
]

const FILE_TYPES = ['STL', '3MF', 'OBJ', 'STEP', 'ZIP', 'RAR']

const MULTICOLOR_OPTIONS: { value: MulticolorStatus | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: 'SINGLE', label: 'Single Color' },
  { value: 'MULTI', label: 'Multicolor' },
  { value: 'UNKNOWN', label: 'Unknown' },
]

const THANGS_OPTIONS: { value: boolean | undefined; label: string }[] = [
  { value: undefined, label: 'All' },
  { value: true, label: 'Linked' },
  { value: false, label: 'Not Linked' },
]

export function FilterSidebar({ filters, onChange, onClearAll, isOpen, onClose }: FilterSidebarProps) {
  const { data: channelsData } = useChannels({ page_size: 100 })

  const handleStatusChange = (status: DesignStatus) => {
    onChange({
      ...filters,
      status: filters.status === status ? undefined : status,
      page: 1,
    })
  }

  const handleChannelChange = (channelId: string) => {
    onChange({
      ...filters,
      channel_id: channelId || undefined,
      page: 1,
    })
  }

  const handleFileTypeChange = (fileType: string) => {
    onChange({
      ...filters,
      file_type: filters.file_type === fileType ? undefined : fileType,
      page: 1,
    })
  }

  const handleMulticolorChange = (multicolor: MulticolorStatus | undefined) => {
    onChange({
      ...filters,
      multicolor,
      page: 1,
    })
  }

  const handleThangsChange = (hasLink: boolean | undefined) => {
    onChange({
      ...filters,
      has_thangs_link: hasLink,
      page: 1,
    })
  }

  const hasActiveFilters = !!(
    filters.status ||
    filters.channel_id ||
    filters.file_type ||
    filters.multicolor ||
    filters.has_thangs_link !== undefined ||
    filters.q ||
    filters.designer
  )

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:sticky inset-y-0 left-0 lg:top-0 z-50 lg:z-auto
          w-64 bg-bg-secondary border-r border-bg-tertiary
          transform transition-transform duration-200 ease-in-out
          lg:transform-none lg:transition-none
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col h-full lg:h-[calc(100vh-3.5rem)] overflow-hidden
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <h2 className="font-semibold text-text-primary">Filters</h2>
          <button
            onClick={onClose}
            className="lg:hidden text-text-secondary hover:text-text-primary"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Scrollable filters area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          {/* Status Filter */}
          <FilterSection title="Status">
            <div className="space-y-2">
              {STATUSES.map(({ value, label }) => (
                <label key={value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filters.status === value}
                    onChange={() => handleStatusChange(value)}
                    className="rounded border-bg-tertiary bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
                  />
                  <span className="text-sm text-text-secondary">{label}</span>
                </label>
              ))}
            </div>
          </FilterSection>

          {/* Channel Filter */}
          <FilterSection title="Channel">
            <select
              value={filters.channel_id || ''}
              onChange={(e) => handleChannelChange(e.target.value)}
              className="w-full bg-bg-tertiary border-0 rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary"
            >
              <option value="">All Channels</option>
              {channelsData?.items.map((channel) => (
                <option key={channel.id} value={channel.id}>
                  {channel.title}
                </option>
              ))}
            </select>
          </FilterSection>

          {/* File Type Filter */}
          <FilterSection title="File Type">
            <div className="space-y-2">
              {FILE_TYPES.map((type) => (
                <label key={type} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={filters.file_type === type}
                    onChange={() => handleFileTypeChange(type)}
                    className="rounded border-bg-tertiary bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
                  />
                  <span className="text-sm text-text-secondary">{type}</span>
                </label>
              ))}
            </div>
          </FilterSection>

          {/* Thangs Status Filter */}
          <FilterSection title="Thangs Link">
            <div className="space-y-2">
              {THANGS_OPTIONS.map(({ value, label }) => (
                <label key={label} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="thangs"
                    checked={filters.has_thangs_link === value}
                    onChange={() => handleThangsChange(value)}
                    className="border-bg-tertiary bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
                  />
                  <span className="text-sm text-text-secondary">{label}</span>
                </label>
              ))}
            </div>
          </FilterSection>

          {/* Multicolor Filter */}
          <FilterSection title="Color Type">
            <div className="space-y-2">
              {MULTICOLOR_OPTIONS.map(({ value, label }) => (
                <label key={label} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="multicolor"
                    checked={filters.multicolor === value}
                    onChange={() => handleMulticolorChange(value)}
                    className="border-bg-tertiary bg-bg-tertiary text-accent-primary focus:ring-accent-primary"
                  />
                  <span className="text-sm text-text-secondary">{label}</span>
                </label>
              ))}
            </div>
          </FilterSection>
        </div>

        {/* Footer with clear button */}
        {hasActiveFilters && (
          <div className="p-4 border-t border-bg-tertiary">
            <button
              onClick={onClearAll}
              className="w-full text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              Clear All Filters
            </button>
          </div>
        )}
      </aside>
    </>
  )
}

function FilterSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-medium text-text-primary mb-2">{title}</h3>
      {children}
    </div>
  )
}

function CloseIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
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
  )
}
