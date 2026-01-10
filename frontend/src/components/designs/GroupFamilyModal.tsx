import { useState } from 'react'
import { useFamilies, useGroupDesigns } from '@/hooks/useFamilies'
import type { DesignListItem } from '@/types/design'
import type { Family } from '@/types/family'

interface GroupFamilyModalProps {
  designs: DesignListItem[]
  onClose: () => void
  onSuccess: () => void
}

export function GroupFamilyModal({ designs, onClose, onSuccess }: GroupFamilyModalProps) {
  const [mode, setMode] = useState<'new' | 'existing'>('new')
  const [newFamilyName, setNewFamilyName] = useState('')
  const [selectedFamilyId, setSelectedFamilyId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [error, setError] = useState<string | null>(null)

  const { data: familiesData, isLoading: familiesLoading } = useFamilies({ limit: 50 })
  const groupMutation = useGroupDesigns()

  const designIds = designs.map((d) => d.id)

  // Filter families based on search query
  const filteredFamilies = familiesData?.items.filter(
    (f) =>
      f.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.display_designer.toLowerCase().includes(searchQuery.toLowerCase())
  ) || []

  // Auto-suggest family name from the first design
  const suggestedName = designs.length > 0 ? extractBaseName(designs[0].display_title) : ''

  const handleCreateNewFamily = async () => {
    if (!newFamilyName.trim()) {
      setError('Please enter a family name')
      return
    }

    setError(null)
    try {
      await groupMutation.mutateAsync({
        design_ids: designIds,
        family_name: newFamilyName.trim(),
      })
      onSuccess()
    } catch (err) {
      setError((err as Error).message || 'Failed to create family')
    }
  }

  const handleAddToExistingFamily = async () => {
    if (!selectedFamilyId) {
      setError('Please select a family')
      return
    }

    setError(null)
    try {
      await groupMutation.mutateAsync({
        design_ids: designIds,
        family_id: selectedFamilyId,
      })
      onSuccess()
    } catch (err) {
      setError((err as Error).message || 'Failed to add to family')
    }
  }

  const handleSubmit = () => {
    if (mode === 'new') {
      handleCreateNewFamily()
    } else {
      handleAddToExistingFamily()
    }
  }

  // Get designer info from selected designs
  const designers = [...new Set(designs.map((d) => d.display_designer))]
  const designerText = designers.length === 1 ? designers[0] : `${designers.length} designers`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-bg-tertiary">
          <div className="flex items-center gap-3">
            <FamilyIcon className="w-6 h-6 text-purple-400" />
            <h2 className="text-lg font-semibold text-text-primary">
              Group into Family
            </h2>
          </div>
          <p className="text-sm text-text-muted mt-1">
            Group {designs.length} design{designs.length !== 1 ? 's' : ''} by {designerText}
          </p>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Selected Designs Preview */}
          <div>
            <h3 className="text-sm font-medium text-text-muted mb-2">Selected Designs</h3>
            <div className="bg-bg-tertiary rounded-lg p-3 max-h-32 overflow-y-auto space-y-1">
              {designs.slice(0, 5).map((design) => (
                <div key={design.id} className="text-sm text-text-secondary truncate">
                  {design.display_title}
                </div>
              ))}
              {designs.length > 5 && (
                <div className="text-sm text-text-muted">
                  +{designs.length - 5} more...
                </div>
              )}
            </div>
          </div>

          {/* Mode Selection */}
          <div className="flex gap-2">
            <button
              onClick={() => setMode('new')}
              className={`flex-1 px-4 py-2 rounded text-sm font-medium transition-colors ${
                mode === 'new'
                  ? 'bg-purple-500/20 text-purple-400 border-2 border-purple-500'
                  : 'bg-bg-tertiary text-text-secondary hover:text-text-primary border-2 border-transparent'
              }`}
            >
              Create New Family
            </button>
            <button
              onClick={() => setMode('existing')}
              className={`flex-1 px-4 py-2 rounded text-sm font-medium transition-colors ${
                mode === 'existing'
                  ? 'bg-purple-500/20 text-purple-400 border-2 border-purple-500'
                  : 'bg-bg-tertiary text-text-secondary hover:text-text-primary border-2 border-transparent'
              }`}
            >
              Add to Existing
            </button>
          </div>

          {/* New Family Form */}
          {mode === 'new' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-muted mb-1">
                  Family Name
                </label>
                <input
                  type="text"
                  value={newFamilyName}
                  onChange={(e) => setNewFamilyName(e.target.value)}
                  placeholder={suggestedName || 'Enter family name...'}
                  className="w-full px-3 py-2 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  autoFocus
                />
                {suggestedName && !newFamilyName && (
                  <button
                    onClick={() => setNewFamilyName(suggestedName)}
                    className="mt-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
                  >
                    Use suggested: "{suggestedName}"
                  </button>
                )}
              </div>
              <p className="text-xs text-text-muted">
                A new family will be created with the selected designs as variants.
              </p>
            </div>
          )}

          {/* Existing Family Selection */}
          {mode === 'existing' && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-muted mb-1">
                  Search Families
                </label>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by name or designer..."
                  className="w-full px-3 py-2 bg-bg-tertiary rounded text-text-primary text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>

              <div className="max-h-48 overflow-y-auto space-y-1">
                {familiesLoading ? (
                  <div className="text-sm text-text-muted text-center py-4">
                    Loading families...
                  </div>
                ) : filteredFamilies.length === 0 ? (
                  <div className="text-sm text-text-muted text-center py-4">
                    {searchQuery ? 'No families found' : 'No families available'}
                  </div>
                ) : (
                  filteredFamilies.map((family) => (
                    <FamilyOption
                      key={family.id}
                      family={family}
                      isSelected={selectedFamilyId === family.id}
                      onSelect={() => setSelectedFamilyId(family.id)}
                    />
                  ))
                )}
              </div>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="text-sm text-accent-danger bg-accent-danger/20 rounded-lg p-3">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-bg-tertiary flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={
              groupMutation.isPending ||
              (mode === 'new' && !newFamilyName.trim()) ||
              (mode === 'existing' && !selectedFamilyId)
            }
            className="px-4 py-2 text-sm rounded bg-purple-500 text-white hover:bg-purple-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {groupMutation.isPending ? (
              <>
                <SpinnerIcon className="w-4 h-4 animate-spin" />
                Grouping...
              </>
            ) : mode === 'new' ? (
              'Create Family'
            ) : (
              'Add to Family'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// Family option component for selection list
interface FamilyOptionProps {
  family: Family
  isSelected: boolean
  onSelect: () => void
}

function FamilyOption({ family, isSelected, onSelect }: FamilyOptionProps) {
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-3 py-2 rounded transition-colors ${
        isSelected
          ? 'bg-purple-500/20 border-2 border-purple-500'
          : 'bg-bg-tertiary hover:bg-bg-tertiary/80 border-2 border-transparent'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-text-primary truncate">
            {family.display_name}
          </div>
          <div className="text-xs text-text-muted">
            by {family.display_designer} • {family.variant_count} variant{family.variant_count !== 1 ? 's' : ''}
          </div>
        </div>
        {isSelected && (
          <CheckIcon className="w-5 h-5 text-purple-400 flex-shrink-0 ml-2" />
        )}
      </div>
    </button>
  )
}

// Extract base name from a design title (removes variant suffixes)
function extractBaseName(title: string): string {
  // Common variant patterns to remove
  const patterns = [
    /\s*[-–]\s*(4[-\s]?color|multi[-\s]?color|single[-\s]?color|remix|v\d+|version\s*\d+).*$/i,
    /\s*\((4[-\s]?color|multi[-\s]?color|single[-\s]?color|remix|v\d+|version\s*\d+)\).*$/i,
    /\s*\[(4[-\s]?color|multi[-\s]?color|single[-\s]?color|remix|v\d+|version\s*\d+)\].*$/i,
  ]

  let baseName = title
  for (const pattern of patterns) {
    baseName = baseName.replace(pattern, '')
  }

  return baseName.trim()
}

// Icon components
function FamilyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  )
}
