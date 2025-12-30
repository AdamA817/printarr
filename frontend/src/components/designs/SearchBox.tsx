import { useState, useEffect, useRef } from 'react'

interface SearchBoxProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  debounceMs?: number
}

export function SearchBox({
  value,
  onChange,
  placeholder = 'Search designs...',
  debounceMs = 300,
}: SearchBoxProps) {
  const [localValue, setLocalValue] = useState(value)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

  // Sync local state when external value changes
  useEffect(() => {
    setLocalValue(value)
  }, [value])

  const handleChange = (newValue: string) => {
    setLocalValue(newValue)

    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    // Debounce the onChange callback
    timeoutRef.current = setTimeout(() => {
      onChange(newValue)
    }, debounceMs)
  }

  const handleClear = () => {
    setLocalValue('')
    onChange('')
    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
  }

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return (
    <div className="relative">
      <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
      <input
        type="text"
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-10 py-2 bg-bg-tertiary border-0 rounded-lg text-text-primary placeholder:text-text-muted focus:ring-2 focus:ring-accent-primary focus:outline-none"
      />
      {localValue && (
        <button
          onClick={handleClear}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
          aria-label="Clear search"
        >
          <ClearIcon />
        </button>
      )}
    </div>
  )
}

function SearchIcon({ className }: { className?: string }) {
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
      className={className}
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

function ClearIcon() {
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
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}
