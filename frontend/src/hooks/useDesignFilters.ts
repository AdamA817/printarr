import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { DesignListParams, DesignStatus, MulticolorStatus, SortField, SortOrder } from '@/types/design'

const VALID_STATUSES: DesignStatus[] = ['DISCOVERED', 'WANTED', 'DOWNLOADING', 'DOWNLOADED', 'ORGANIZED', 'FAILED']
const VALID_MULTICOLORS: MulticolorStatus[] = ['UNKNOWN', 'SINGLE', 'MULTI']
const VALID_SORT_FIELDS: SortField[] = ['created_at', 'canonical_title', 'canonical_designer', 'total_size_bytes']
const VALID_SORT_ORDERS: SortOrder[] = ['ASC', 'DESC']

function parseStatus(value: string | null): DesignStatus | undefined {
  if (value && VALID_STATUSES.includes(value as DesignStatus)) {
    return value as DesignStatus
  }
  return undefined
}

function parseMulticolor(value: string | null): MulticolorStatus | undefined {
  if (value && VALID_MULTICOLORS.includes(value as MulticolorStatus)) {
    return value as MulticolorStatus
  }
  return undefined
}

function parseSortField(value: string | null): SortField | undefined {
  if (value && VALID_SORT_FIELDS.includes(value as SortField)) {
    return value as SortField
  }
  return undefined
}

function parseSortOrder(value: string | null): SortOrder | undefined {
  if (value && VALID_SORT_ORDERS.includes(value as SortOrder)) {
    return value as SortOrder
  }
  return undefined
}

function parseBoolean(value: string | null): boolean | undefined {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

function parseNumber(value: string | null, min = 1): number | undefined {
  if (!value) return undefined
  const num = parseInt(value, 10)
  return isNaN(num) || num < min ? undefined : num
}

export function useDesignFilters(defaultPageSize = 24) {
  const [searchParams, setSearchParams] = useSearchParams()

  // Parse filters from URL params
  const filters: DesignListParams = useMemo(() => ({
    page: parseNumber(searchParams.get('page')) || 1,
    page_size: parseNumber(searchParams.get('page_size')) || defaultPageSize,
    status: parseStatus(searchParams.get('status')),
    channel_id: searchParams.get('channel_id') || undefined,
    file_type: searchParams.get('file_type') || undefined,
    multicolor: parseMulticolor(searchParams.get('multicolor')),
    has_thangs_link: parseBoolean(searchParams.get('has_thangs_link')),
    designer: searchParams.get('designer') || undefined,
    q: searchParams.get('q') || undefined,
    sort_by: parseSortField(searchParams.get('sort_by')) || 'created_at',
    sort_order: parseSortOrder(searchParams.get('sort_order')) || 'DESC',
  }), [searchParams, defaultPageSize])

  // Update filters (merges with existing and updates URL)
  const setFilters = useCallback((newFilters: Partial<DesignListParams>) => {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev)

      // Merge new filters with existing
      const merged = { ...filters, ...newFilters }

      // Update or remove each param
      Object.entries(merged).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') {
          params.delete(key)
        } else if (typeof value === 'boolean') {
          params.set(key, value.toString())
        } else {
          params.set(key, String(value))
        }
      })

      // Remove default values to keep URL clean
      if (params.get('page') === '1') params.delete('page')
      if (params.get('sort_by') === 'created_at') params.delete('sort_by')
      if (params.get('sort_order') === 'DESC') params.delete('sort_order')
      if (params.get('page_size') === String(defaultPageSize)) params.delete('page_size')

      return params
    })
  }, [filters, setSearchParams, defaultPageSize])

  // Remove a specific filter
  const removeFilter = useCallback((key: keyof DesignListParams) => {
    setFilters({ [key]: undefined, page: 1 })
  }, [setFilters])

  // Clear all filters (keep pagination and sorting)
  const clearFilters = useCallback(() => {
    setFilters({
      status: undefined,
      channel_id: undefined,
      file_type: undefined,
      multicolor: undefined,
      has_thangs_link: undefined,
      designer: undefined,
      q: undefined,
      page: 1,
    })
  }, [setFilters])

  // Set page
  const setPage = useCallback((page: number) => {
    setFilters({ page })
  }, [setFilters])

  return {
    filters,
    setFilters,
    removeFilter,
    clearFilters,
    setPage,
  }
}
