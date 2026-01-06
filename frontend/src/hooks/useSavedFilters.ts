import { useState, useCallback, useEffect } from 'react'
import type { DesignListParams } from '@/types/design'

const STORAGE_KEY = 'printarr_saved_filters'

/**
 * A saved custom filter definition
 */
export interface SavedFilter {
  id: string
  label: string
  filters: Partial<DesignListParams>
  createdAt: string
}

/**
 * A single filter condition for the query builder
 */
export interface FilterCondition {
  id: string
  field: FilterField
  operator: FilterOperator
  value: string | string[] | boolean
}

export type FilterField =
  | 'status'
  | 'channel_id'
  | 'import_source_id'
  | 'import_source_folder_id'
  | 'designer'
  | 'file_type'
  | 'has_thangs_link'
  | 'multicolor'
  | 'tags'

export type FilterOperator =
  | 'is'
  | 'is_not'
  | 'contains'
  | 'is_true'
  | 'is_false'

/**
 * Field metadata for the query builder UI
 */
export const FILTER_FIELD_CONFIG: Record<FilterField, {
  label: string
  operators: FilterOperator[]
  valueType: 'select' | 'text' | 'boolean' | 'multi-select'
}> = {
  status: {
    label: 'Status',
    operators: ['is', 'is_not'],
    valueType: 'select',
  },
  channel_id: {
    label: 'Channel',
    operators: ['is', 'is_not'],
    valueType: 'select',
  },
  import_source_id: {
    label: 'Import Source',
    operators: ['is', 'is_not'],
    valueType: 'select',
  },
  import_source_folder_id: {
    label: 'Import Folder',
    operators: ['is', 'is_not'],
    valueType: 'select',
  },
  designer: {
    label: 'Designer',
    operators: ['is', 'contains'],
    valueType: 'text',
  },
  file_type: {
    label: 'File Type',
    operators: ['is', 'contains'],
    valueType: 'text',
  },
  has_thangs_link: {
    label: 'Thangs Link',
    operators: ['is_true', 'is_false'],
    valueType: 'boolean',
  },
  multicolor: {
    label: 'Color Type',
    operators: ['is'],
    valueType: 'select',
  },
  tags: {
    label: 'Tags',
    operators: ['contains'],
    valueType: 'multi-select',
  },
}

/**
 * Predefined filter presets (like Radarr's built-in filters)
 */
export const PREDEFINED_FILTERS: { id: string; label: string; filters: Partial<DesignListParams> }[] = [
  { id: 'all', label: 'All', filters: {} },
  { id: 'discovered', label: 'Discovered', filters: { status: 'DISCOVERED' } },
  { id: 'wanted', label: 'Wanted', filters: { status: 'WANTED' } },
  { id: 'downloading', label: 'Downloading', filters: { status: 'DOWNLOADING' } },
  { id: 'downloaded', label: 'Downloaded', filters: { status: 'DOWNLOADED' } },
  { id: 'organized', label: 'Organized', filters: { status: 'ORGANIZED' } },
  { id: 'failed', label: 'Failed', filters: { status: 'FAILED' } },
]

/**
 * Convert filter conditions to DesignListParams
 */
export function conditionsToParams(conditions: FilterCondition[]): Partial<DesignListParams> {
  const params: Partial<DesignListParams> = {}

  for (const condition of conditions) {
    const { field, operator, value } = condition

    // Handle boolean operators
    if (operator === 'is_true') {
      if (field === 'has_thangs_link') params.has_thangs_link = true
      continue
    }
    if (operator === 'is_false') {
      if (field === 'has_thangs_link') params.has_thangs_link = false
      continue
    }

    // Handle regular operators
    switch (field) {
      case 'status':
        if (operator === 'is' && typeof value === 'string') {
          params.status = value as DesignListParams['status']
        }
        break
      case 'channel_id':
        if (operator === 'is' && typeof value === 'string') {
          params.channel_id = value
        }
        break
      case 'import_source_id':
        if (operator === 'is' && typeof value === 'string') {
          params.import_source_id = value
        }
        break
      case 'import_source_folder_id':
        if (operator === 'is' && typeof value === 'string') {
          params.import_source_folder_id = value
        }
        break
      case 'designer':
        if (typeof value === 'string') {
          params.designer = value
        }
        break
      case 'file_type':
        if (typeof value === 'string') {
          params.file_type = value
        }
        break
      case 'multicolor':
        if (operator === 'is' && typeof value === 'string') {
          params.multicolor = value as DesignListParams['multicolor']
        }
        break
      case 'tags':
        if (Array.isArray(value)) {
          params.tags = value
        }
        break
    }
  }

  return params
}

/**
 * Hook for managing saved custom filters in localStorage
 */
export function useSavedFilters() {
  const [savedFilters, setSavedFilters] = useState<SavedFilter[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      return stored ? JSON.parse(stored) : []
    } catch {
      return []
    }
  })

  // Persist to localStorage whenever savedFilters changes
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(savedFilters))
    } catch (e) {
      console.error('Failed to save filters to localStorage:', e)
    }
  }, [savedFilters])

  const saveFilter = useCallback((label: string, filters: Partial<DesignListParams>) => {
    const newFilter: SavedFilter = {
      id: `custom_${Date.now()}`,
      label,
      filters,
      createdAt: new Date().toISOString(),
    }
    setSavedFilters((prev) => [...prev, newFilter])
    return newFilter
  }, [])

  const updateFilter = useCallback((id: string, updates: Partial<Pick<SavedFilter, 'label' | 'filters'>>) => {
    setSavedFilters((prev) =>
      prev.map((f) => (f.id === id ? { ...f, ...updates } : f))
    )
  }, [])

  const deleteFilter = useCallback((id: string) => {
    setSavedFilters((prev) => prev.filter((f) => f.id !== id))
  }, [])

  const getFilterById = useCallback(
    (id: string) => {
      // Check predefined first
      const predefined = PREDEFINED_FILTERS.find((f) => f.id === id)
      if (predefined) return predefined

      // Then check saved
      return savedFilters.find((f) => f.id === id)
    },
    [savedFilters]
  )

  return {
    savedFilters,
    saveFilter,
    updateFilter,
    deleteFilter,
    getFilterById,
    predefinedFilters: PREDEFINED_FILTERS,
  }
}
