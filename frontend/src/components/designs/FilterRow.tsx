import { useState } from 'react'
import {
  type FilterCondition,
  type FilterField,
  type FilterOperator,
  FILTER_FIELD_CONFIG,
} from '@/hooks/useSavedFilters'
import { useChannels } from '@/hooks/useChannels'
import { useImportSources } from '@/hooks/useImportSources'
import { useAllFolders } from '@/hooks/useAllFolders'
import { useDesignerAutocomplete } from '@/hooks/useDesignerAutocomplete'
import type { DesignStatus, MulticolorStatus } from '@/types/design'

interface FilterRowProps {
  condition: FilterCondition
  onChange: (condition: FilterCondition) => void
  onRemove: () => void
  canRemove: boolean
}

const STATUS_OPTIONS: { value: DesignStatus; label: string }[] = [
  { value: 'DISCOVERED', label: 'Discovered' },
  { value: 'WANTED', label: 'Wanted' },
  { value: 'DOWNLOADING', label: 'Downloading' },
  { value: 'DOWNLOADED', label: 'Downloaded' },
  { value: 'ORGANIZED', label: 'Organized' },
  { value: 'FAILED', label: 'Failed' },
]

const MULTICOLOR_OPTIONS: { value: MulticolorStatus; label: string }[] = [
  { value: 'UNKNOWN', label: 'Unknown' },
  { value: 'SINGLE', label: 'Single Color' },
  { value: 'MULTI', label: 'Multi Color' },
]

const FIELD_OPTIONS: { value: FilterField; label: string }[] = Object.entries(
  FILTER_FIELD_CONFIG
).map(([value, config]) => ({
  value: value as FilterField,
  label: config.label,
}))

export function FilterRow({ condition, onChange, onRemove, canRemove }: FilterRowProps) {
  const fieldConfig = FILTER_FIELD_CONFIG[condition.field]
  const operators = fieldConfig.operators

  // Data for select dropdowns
  const { data: channelsData } = useChannels()
  const { data: sourcesData } = useImportSources()
  const { data: foldersData } = useAllFolders(
    condition.field === 'import_source_folder_id' ? undefined : undefined
  )

  // Designer autocomplete
  const [designerSearch, setDesignerSearch] = useState(
    typeof condition.value === 'string' ? condition.value : ''
  )
  const { data: designerSuggestions } = useDesignerAutocomplete(designerSearch)
  const [showDesignerDropdown, setShowDesignerDropdown] = useState(false)

  const handleFieldChange = (newField: FilterField) => {
    const newConfig = FILTER_FIELD_CONFIG[newField]
    const defaultOperator = newConfig.operators[0]
    const defaultValue = newConfig.valueType === 'boolean' ? true : ''

    onChange({
      ...condition,
      field: newField,
      operator: defaultOperator,
      value: defaultValue,
    })
  }

  const handleOperatorChange = (newOperator: FilterOperator) => {
    onChange({
      ...condition,
      operator: newOperator,
    })
  }

  const handleValueChange = (newValue: string | string[] | boolean) => {
    onChange({
      ...condition,
      value: newValue,
    })
  }

  // Render value input based on field type
  const renderValueInput = () => {
    const { field, value } = condition

    // Boolean fields use the operator itself (is_true/is_false)
    if (fieldConfig.valueType === 'boolean') {
      return null
    }

    // Select fields
    if (fieldConfig.valueType === 'select') {
      let options: { value: string; label: string }[] = []

      if (field === 'status') {
        options = STATUS_OPTIONS
      } else if (field === 'multicolor') {
        options = MULTICOLOR_OPTIONS
      } else if (field === 'channel_id') {
        options = (channelsData?.items || []).map((c) => ({
          value: c.id,
          label: c.title,
        }))
      } else if (field === 'import_source_id') {
        options = (sourcesData?.items || []).map((s) => ({
          value: s.id,
          label: s.name,
        }))
      } else if (field === 'import_source_folder_id') {
        options = (foldersData?.items || []).map((f) => ({
          value: f.id,
          label: f.name ? `${f.source_name} / ${f.name}` : f.source_name,
        }))
      }

      return (
        <select
          value={typeof value === 'string' ? value : ''}
          onChange={(e) => handleValueChange(e.target.value)}
          className="flex-1 bg-bg-tertiary border-0 rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary"
        >
          <option value="">Select...</option>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )
    }

    // Text field with autocomplete for designer
    if (field === 'designer') {
      return (
        <div className="relative flex-1">
          <input
            type="text"
            value={designerSearch}
            onChange={(e) => {
              setDesignerSearch(e.target.value)
              handleValueChange(e.target.value)
              setShowDesignerDropdown(true)
            }}
            onFocus={() => setShowDesignerDropdown(true)}
            onBlur={() => setTimeout(() => setShowDesignerDropdown(false), 200)}
            placeholder="Enter designer name..."
            className="w-full bg-bg-tertiary border-0 rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary"
          />
          {showDesignerDropdown && designerSuggestions?.items && designerSuggestions.items.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-bg-secondary border border-border-primary rounded-lg shadow-lg z-50 max-h-48 overflow-auto">
              {designerSuggestions.items.map((suggestion) => (
                <button
                  key={suggestion.name}
                  type="button"
                  onClick={() => {
                    setDesignerSearch(suggestion.name)
                    handleValueChange(suggestion.name)
                    setShowDesignerDropdown(false)
                  }}
                  className="w-full px-3 py-2 text-left text-sm text-text-primary hover:bg-bg-tertiary flex justify-between"
                >
                  <span>{suggestion.name}</span>
                  <span className="text-text-muted">({suggestion.count})</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )
    }

    // Plain text field
    return (
      <input
        type="text"
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => handleValueChange(e.target.value)}
        placeholder="Enter value..."
        className="flex-1 bg-bg-tertiary border-0 rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary"
      />
    )
  }

  return (
    <div className="flex items-center gap-2">
      {/* Field selector */}
      <select
        value={condition.field}
        onChange={(e) => handleFieldChange(e.target.value as FilterField)}
        className="w-40 bg-bg-tertiary border-0 rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary"
      >
        {FIELD_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Operator selector */}
      <select
        value={condition.operator}
        onChange={(e) => handleOperatorChange(e.target.value as FilterOperator)}
        className="w-28 bg-bg-tertiary border-0 rounded px-3 py-2 text-sm text-text-primary focus:ring-accent-primary"
      >
        {operators.map((op) => (
          <option key={op} value={op}>
            {formatOperator(op)}
          </option>
        ))}
      </select>

      {/* Value input */}
      {renderValueInput()}

      {/* Remove button */}
      <button
        onClick={onRemove}
        disabled={!canRemove}
        className="p-2 text-text-muted hover:text-accent-danger transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        title="Remove condition"
      >
        <MinusIcon />
      </button>
    </div>
  )
}

function formatOperator(op: FilterOperator): string {
  switch (op) {
    case 'is':
      return 'is'
    case 'is_not':
      return 'is not'
    case 'contains':
      return 'contains'
    case 'is_true':
      return 'is true'
    case 'is_false':
      return 'is false'
    default:
      return op
  }
}

function MinusIcon() {
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
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
}
