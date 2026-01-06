import { useState } from 'react'
import { FilterRow } from './FilterRow'
import {
  type FilterCondition,
  type FilterField,
  conditionsToParams,
} from '@/hooks/useSavedFilters'
import type { DesignListParams } from '@/types/design'

interface CustomFilterModalProps {
  isOpen: boolean
  onClose: () => void
  onApply: (filters: Partial<DesignListParams>) => void
  onSave: (label: string, filters: Partial<DesignListParams>) => void
  initialConditions?: FilterCondition[]
}

function generateId(): string {
  return `cond_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
}

function createDefaultCondition(): FilterCondition {
  return {
    id: generateId(),
    field: 'status' as FilterField,
    operator: 'is',
    value: '',
  }
}

export function CustomFilterModal({
  isOpen,
  onClose,
  onApply,
  onSave,
  initialConditions,
}: CustomFilterModalProps) {
  const [conditions, setConditions] = useState<FilterCondition[]>(
    initialConditions || [createDefaultCondition()]
  )
  const [filterLabel, setFilterLabel] = useState('')
  const [showSaveForm, setShowSaveForm] = useState(false)

  if (!isOpen) return null

  const handleAddCondition = () => {
    setConditions([...conditions, createDefaultCondition()])
  }

  const handleRemoveCondition = (id: string) => {
    if (conditions.length > 1) {
      setConditions(conditions.filter((c) => c.id !== id))
    }
  }

  const handleUpdateCondition = (updated: FilterCondition) => {
    setConditions(conditions.map((c) => (c.id === updated.id ? updated : c)))
  }

  const handleApply = () => {
    const params = conditionsToParams(conditions)
    onApply(params)
    onClose()
  }

  const handleSave = () => {
    if (!filterLabel.trim()) return
    const params = conditionsToParams(conditions)
    onSave(filterLabel.trim(), params)
    setFilterLabel('')
    setShowSaveForm(false)
    onClose()
  }

  const handleClose = () => {
    setConditions([createDefaultCondition()])
    setFilterLabel('')
    setShowSaveForm(false)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-bg-secondary rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border-primary">
          <h2 className="text-lg font-semibold text-text-primary">Custom Filter</h2>
          <button
            onClick={handleClose}
            className="p-1 text-text-muted hover:text-text-primary transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 space-y-4">
          <div className="text-sm text-text-muted mb-4">
            Build a custom filter by adding conditions. All conditions must match (AND logic).
          </div>

          {/* Filter conditions */}
          <div className="space-y-3">
            {conditions.map((condition) => (
              <FilterRow
                key={condition.id}
                condition={condition}
                onChange={handleUpdateCondition}
                onRemove={() => handleRemoveCondition(condition.id)}
                canRemove={conditions.length > 1}
              />
            ))}
          </div>

          {/* Add condition button */}
          <button
            onClick={handleAddCondition}
            className="flex items-center gap-2 px-3 py-2 text-sm text-accent-primary hover:bg-accent-primary/10 rounded transition-colors"
          >
            <PlusIcon />
            Add condition
          </button>

          {/* Save form */}
          {showSaveForm && (
            <div className="mt-4 p-4 bg-bg-tertiary rounded-lg">
              <label className="block text-sm text-text-muted mb-2">Filter name</label>
              <input
                type="text"
                value={filterLabel}
                onChange={(e) => setFilterLabel(e.target.value)}
                placeholder="Enter a name for this filter..."
                className="w-full bg-bg-secondary border border-border-primary rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary focus:border-accent-primary"
                autoFocus
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border-primary">
          <button
            onClick={() => setShowSaveForm(!showSaveForm)}
            className="text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            {showSaveForm ? 'Cancel save' : 'Save as...'}
          </button>

          <div className="flex items-center gap-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>

            {showSaveForm ? (
              <button
                onClick={handleSave}
                disabled={!filterLabel.trim()}
                className="px-4 py-2 text-sm bg-accent-primary text-white rounded hover:bg-accent-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Save Filter
              </button>
            ) : (
              <button
                onClick={handleApply}
                className="px-4 py-2 text-sm bg-accent-primary text-white rounded hover:bg-accent-primary/90 transition-colors"
              >
                Apply Filter
              </button>
            )}
          </div>
        </div>
      </div>
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

function PlusIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}
