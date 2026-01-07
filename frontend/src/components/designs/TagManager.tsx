/**
 * TagManager - Tag management UI for design detail page (v0.7)
 *
 * Features:
 * - Display existing tags as chips with source indicator
 * - Remove tag with × button
 * - Add tag via autocomplete input
 * - Search/create new tags
 * - Show tag source (auto vs user) with subtle indicator
 * - Max tags indicator
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { useTagSearch, useAddTagsToDesign, useRemoveTagFromDesign } from '@/hooks/useTags'
import type { DesignTag, TagSummary, TagSource, Tag } from '@/types/design'

interface TagManagerProps {
  designId: string
  tags: DesignTag[] | TagSummary[]
  maxTags?: number
  readOnly?: boolean
}

// Source indicator colors
const sourceConfig: Record<TagSource, { label: string; className: string }> = {
  AUTO_CAPTION: { label: 'caption', className: 'text-blue-400' },
  AUTO_FILENAME: { label: 'filename', className: 'text-purple-400' },
  AUTO_THANGS: { label: 'thangs', className: 'text-green-400' },
  AUTO_AI: { label: 'AI', className: 'text-purple-400' },
  USER: { label: 'user', className: 'text-text-muted' },
}

interface TagChipProps {
  tag: DesignTag | TagSummary
  onRemove?: () => void
  isRemoving?: boolean
}

function TagChip({ tag, onRemove, isRemoving }: TagChipProps) {
  const source = sourceConfig[tag.source]

  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-bg-tertiary text-sm group">
      <span className="text-text-primary">{tag.name}</span>
      {tag.category && (
        <span className="text-[10px] text-text-muted">({tag.category})</span>
      )}
      {tag.source !== 'USER' && (
        <span className={`text-[9px] ${source.className}`} title={`Added from ${source.label}`}>
          {source.label}
        </span>
      )}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          disabled={isRemoving}
          className="ml-0.5 text-text-muted hover:text-accent-danger transition-colors disabled:opacity-50"
          aria-label={`Remove ${tag.name} tag`}
        >
          <CloseIcon className="w-3.5 h-3.5" />
        </button>
      )}
    </span>
  )
}

interface TagInputProps {
  onAddTag: (tagName: string) => void
  isAdding: boolean
  existingTags: string[]
  maxTags: number
  currentCount: number
}

function TagInput({ onAddTag, isAdding, existingTags, maxTags, currentCount }: TagInputProps) {
  const [query, setQuery] = useState('')
  const [isOpen, setIsOpen] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const { data: searchResults, isLoading } = useTagSearch(query, 10)

  // Filter out already assigned tags
  const filteredResults = searchResults?.items.filter(
    (tag) => !existingTags.includes(tag.name.toLowerCase())
  ) || []

  // Check if query matches existing tag or can create new
  const canCreateNew = query.length > 0 &&
    !filteredResults.some((t) => t.name.toLowerCase() === query.toLowerCase()) &&
    !existingTags.includes(query.toLowerCase())

  const options: Array<{ type: 'existing' | 'create'; tag?: Tag; name: string }> = [
    ...filteredResults.map((tag) => ({ type: 'existing' as const, tag, name: tag.name })),
    ...(canCreateNew ? [{ type: 'create' as const, name: query }] : []),
  ]

  const handleSelect = useCallback((option: typeof options[number]) => {
    onAddTag(option.name)
    setQuery('')
    setIsOpen(false)
    setSelectedIndex(0)
    inputRef.current?.focus()
  }, [onAddTag])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen && e.key === 'ArrowDown') {
      setIsOpen(true)
      return
    }

    if (isOpen) {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setSelectedIndex((i) => Math.min(i + 1, options.length - 1))
          break
        case 'ArrowUp':
          e.preventDefault()
          setSelectedIndex((i) => Math.max(i - 1, 0))
          break
        case 'Enter':
          e.preventDefault()
          if (options[selectedIndex]) {
            handleSelect(options[selectedIndex])
          }
          break
        case 'Escape':
          setIsOpen(false)
          setSelectedIndex(0)
          break
      }
    } else if (e.key === 'Enter' && query.trim() && canCreateNew) {
      e.preventDefault()
      handleSelect({ type: 'create', name: query.trim() })
    }
  }

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isAtLimit = currentCount >= maxTags

  return (
    <div className="relative">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setIsOpen(e.target.value.length > 0)
              setSelectedIndex(0)
            }}
            onFocus={() => query.length > 0 && setIsOpen(true)}
            onKeyDown={handleKeyDown}
            disabled={isAdding || isAtLimit}
            placeholder={isAtLimit ? 'Max tags reached' : 'Search or create tag...'}
            className="w-full px-3 py-2 bg-bg-tertiary rounded-md text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary disabled:opacity-50"
          />
          {isLoading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <LoadingSpinner className="w-4 h-4" />
            </div>
          )}
        </div>

        {/* Tag count indicator */}
        <span className={`text-xs whitespace-nowrap ${isAtLimit ? 'text-accent-warning' : 'text-text-muted'}`}>
          {currentCount}/{maxTags}
        </span>
      </div>

      {/* Dropdown */}
      {isOpen && options.length > 0 && (
        <div
          ref={dropdownRef}
          className="absolute z-10 mt-1 w-full bg-bg-secondary border border-bg-tertiary rounded-md shadow-lg max-h-60 overflow-y-auto"
        >
          {options.map((option, index) => (
            <button
              key={option.type === 'existing' ? option.tag?.id : `create-${option.name}`}
              type="button"
              onClick={() => handleSelect(option)}
              className={`w-full px-3 py-2 text-left text-sm flex items-center gap-2 ${
                index === selectedIndex
                  ? 'bg-accent-primary/20 text-text-primary'
                  : 'text-text-secondary hover:bg-bg-tertiary'
              }`}
            >
              {option.type === 'create' ? (
                <>
                  <PlusIcon className="w-4 h-4 text-accent-primary" />
                  <span>Create &quot;{option.name}&quot;</span>
                </>
              ) : (
                <>
                  <TagIcon className="w-4 h-4 text-text-muted" />
                  <span>{option.name}</span>
                  {option.tag?.category && (
                    <span className="text-xs text-text-muted">({option.tag.category})</span>
                  )}
                  {option.tag && option.tag.usage_count > 0 && (
                    <span className="text-xs text-text-muted ml-auto">{option.tag.usage_count}</span>
                  )}
                </>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function TagManager({ designId, tags, maxTags = 20, readOnly = false }: TagManagerProps) {
  const addTagsMutation = useAddTagsToDesign()
  const removeTagMutation = useRemoveTagFromDesign()
  const [removingTagId, setRemovingTagId] = useState<string | null>(null)

  const existingTagNames = tags.map((t) => t.name.toLowerCase())

  const handleAddTag = async (tagName: string) => {
    try {
      await addTagsMutation.mutateAsync({
        designId,
        tags: [tagName],
        source: 'USER',
      })
    } catch (error) {
      console.error('Failed to add tag:', error)
    }
  }

  const handleRemoveTag = async (tag: DesignTag | TagSummary) => {
    setRemovingTagId(tag.id)
    try {
      await removeTagMutation.mutateAsync({ designId, tagId: tag.id })
    } catch (error) {
      console.error('Failed to remove tag:', error)
    } finally {
      setRemovingTagId(null)
    }
  }

  // Group tags by source for summary
  const sourceGroups = tags.reduce(
    (acc, tag) => {
      const source = tag.source
      acc[source] = (acc[source] || 0) + 1
      return acc
    },
    {} as Record<TagSource, number>
  )

  return (
    <div className="space-y-3">
      {/* Tag List */}
      {tags.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <TagChip
              key={tag.id}
              tag={tag}
              onRemove={readOnly ? undefined : () => handleRemoveTag(tag)}
              isRemoving={removingTagId === tag.id}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-text-muted">No tags assigned</p>
      )}

      {/* Tag Input */}
      {!readOnly && (
        <TagInput
          onAddTag={handleAddTag}
          isAdding={addTagsMutation.isPending}
          existingTags={existingTagNames}
          maxTags={maxTags}
          currentCount={tags.length}
        />
      )}

      {/* Source Summary */}
      {tags.length > 0 && (
        <div className="text-xs text-text-muted flex flex-wrap gap-2">
          {Object.entries(sourceGroups).map(([source, count]) => {
            const config = sourceConfig[source as TagSource]
            return (
              <span key={source} className={config.className}>
                {config.label}({count})
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}

// Compact tag display for cards
interface TagListProps {
  tags: TagSummary[]
  maxVisible?: number
}

export function TagList({ tags, maxVisible = 3 }: TagListProps) {
  const visible = tags.slice(0, maxVisible)
  const remaining = tags.length - maxVisible

  if (tags.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1">
      {visible.map((tag) => (
        <span
          key={tag.id}
          className="px-1.5 py-0.5 rounded text-[10px] bg-bg-tertiary text-text-secondary"
        >
          {tag.name}
        </span>
      ))}
      {remaining > 0 && (
        <span className="px-1.5 py-0.5 rounded text-[10px] bg-bg-tertiary text-text-muted">
          +{remaining}
        </span>
      )}
    </div>
  )
}

// Icon Components

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  )
}

function TagIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z"
      />
    </svg>
  )
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}
