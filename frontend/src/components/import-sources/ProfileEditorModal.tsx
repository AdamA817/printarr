/**
 * Modal for viewing/editing import profile configuration
 */
import { useState, useEffect } from 'react'
import type {
  ImportProfile,
  ImportProfileCreate,
  ImportProfileConfig,
  ProfileDetectionConfig,
  ProfileTitleConfig,
  ProfilePreviewConfig,
  ProfileIgnoreConfig,
  ProfileAutoTagConfig,
} from '@/types/import-source'

interface ProfileEditorModalProps {
  isOpen: boolean
  profile: ImportProfile | null
  mode: 'view' | 'edit' | 'create' | 'duplicate'
  onClose: () => void
  onSave: (data: ImportProfileCreate) => void
  isSaving: boolean
  error: string | null
}

type TabType = 'detection' | 'title' | 'preview' | 'ignore' | 'autotag'

const defaultConfig: ImportProfileConfig = {
  detection: {
    model_extensions: ['.stl', '.3mf', '.obj', '.step'],
    archive_extensions: ['.zip', '.rar', '.7z'],
    min_model_files: 1,
    structure: 'auto',
    model_subfolders: ['STLs', 'stls', 'Models', 'Supported', 'Unsupported'],
  },
  title: {
    source: 'folder_name',
    strip_patterns: ['(Supported)', '(Unsupported)', '(STLs)', '(Models)'],
    case_transform: 'none',
  },
  preview: {
    folders: ['Renders', 'Images', 'Preview', 'Photos', 'Pictures'],
    wildcard_folders: ['*Renders', '*Preview', '*Images'],
    extensions: ['.jpg', '.jpeg', '.png', '.webp', '.gif'],
    include_root: true,
  },
  ignore: {
    folders: ['Lychee', 'Chitubox', 'Project Files', 'Source', '.git', '__MACOSX'],
    extensions: ['.lys', '.ctb', '.gcode', '.blend', '.zcode', '.chitubox'],
    patterns: ['.DS_Store', 'Thumbs.db', '*.tmp'],
  },
  auto_tags: {
    from_subfolders: true,
    from_filename: false,
    subfolder_levels: 2,
    strip_patterns: ['Tier$', '^\\d{4}-\\d{2}'],
  },
}

export function ProfileEditorModal({
  isOpen,
  profile,
  mode,
  onClose,
  onSave,
  isSaving,
  error,
}: ProfileEditorModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('detection')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [config, setConfig] = useState<ImportProfileConfig>(defaultConfig)

  const isReadOnly = mode === 'view'
  const title = {
    view: 'View Profile',
    edit: 'Edit Profile',
    create: 'Create Profile',
    duplicate: 'Duplicate Profile',
  }[mode]

  // Initialize form when modal opens
  useEffect(() => {
    if (isOpen && profile) {
      setName(mode === 'duplicate' ? `${profile.name} (Copy)` : profile.name)
      setDescription(profile.description || '')
      setConfig(profile.config)
    } else if (isOpen && mode === 'create') {
      setName('')
      setDescription('')
      setConfig(defaultConfig)
    }
    setActiveTab('detection')
  }, [isOpen, profile, mode])

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({ name, description: description || undefined, config })
  }

  const updateDetection = (updates: Partial<ProfileDetectionConfig>) => {
    setConfig((prev) => ({ ...prev, detection: { ...prev.detection, ...updates } }))
  }

  const updateTitle = (updates: Partial<ProfileTitleConfig>) => {
    setConfig((prev) => ({ ...prev, title: { ...prev.title, ...updates } }))
  }

  const updatePreview = (updates: Partial<ProfilePreviewConfig>) => {
    setConfig((prev) => ({ ...prev, preview: { ...prev.preview, ...updates } }))
  }

  const updateIgnore = (updates: Partial<ProfileIgnoreConfig>) => {
    setConfig((prev) => ({ ...prev, ignore: { ...prev.ignore, ...updates } }))
  }

  const updateAutoTags = (updates: Partial<ProfileAutoTagConfig>) => {
    setConfig((prev) => ({ ...prev, auto_tags: { ...prev.auto_tags, ...updates } }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary flex-shrink-0">
          <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
          <button
            onClick={onClose}
            className="p-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded transition-colors"
            aria-label="Close"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          {/* Basic Info */}
          <div className="p-4 border-b border-bg-tertiary flex-shrink-0">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Name {!isReadOnly && <span className="text-accent-danger">*</span>}
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isReadOnly}
                  className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-primary mb-1">
                  Description
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isReadOnly}
                  placeholder="Optional description"
                  className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                />
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="border-b border-bg-tertiary px-4 flex-shrink-0">
            <nav className="flex gap-4">
              {(['detection', 'title', 'preview', 'ignore', 'autotag'] as TabType[]).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={`py-2 px-1 text-sm font-medium border-b-2 transition-colors capitalize ${
                    activeTab === tab
                      ? 'border-accent-primary text-accent-primary'
                      : 'border-transparent text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {tab === 'autotag' ? 'Auto-Tags' : tab}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {/* Detection Tab */}
            {activeTab === 'detection' && (
              <div className="space-y-4">
                <ArrayInput
                  label="Model Extensions"
                  value={config.detection.model_extensions}
                  onChange={(v) => updateDetection({ model_extensions: v })}
                  disabled={isReadOnly}
                  placeholder=".stl"
                />
                <ArrayInput
                  label="Archive Extensions"
                  value={config.detection.archive_extensions}
                  onChange={(v) => updateDetection({ archive_extensions: v })}
                  disabled={isReadOnly}
                  placeholder=".zip"
                />
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-text-primary mb-1">
                      Minimum Model Files
                    </label>
                    <input
                      type="number"
                      min={1}
                      value={config.detection.min_model_files}
                      onChange={(e) => updateDetection({ min_model_files: parseInt(e.target.value) || 1 })}
                      disabled={isReadOnly}
                      className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-text-primary mb-1">
                      Folder Structure
                    </label>
                    <select
                      value={config.detection.structure}
                      onChange={(e) => updateDetection({ structure: e.target.value as 'nested' | 'flat' | 'auto' })}
                      disabled={isReadOnly}
                      className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                    >
                      <option value="auto">Auto-detect</option>
                      <option value="flat">Flat (files at root)</option>
                      <option value="nested">Nested (subfolders)</option>
                    </select>
                  </div>
                </div>
                <ArrayInput
                  label="Model Subfolders"
                  value={config.detection.model_subfolders}
                  onChange={(v) => updateDetection({ model_subfolders: v })}
                  disabled={isReadOnly}
                  placeholder="STLs"
                  hint="Subfolder names that may contain model files"
                />
              </div>
            )}

            {/* Title Tab */}
            {activeTab === 'title' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1">
                    Title Source
                  </label>
                  <select
                    value={config.title.source}
                    onChange={(e) => updateTitle({ source: e.target.value as 'folder_name' | 'parent_folder' | 'filename' })}
                    disabled={isReadOnly}
                    className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                  >
                    <option value="folder_name">Folder Name</option>
                    <option value="parent_folder">Parent Folder</option>
                    <option value="filename">First Model Filename</option>
                  </select>
                </div>
                <ArrayInput
                  label="Strip Patterns"
                  value={config.title.strip_patterns}
                  onChange={(v) => updateTitle({ strip_patterns: v })}
                  disabled={isReadOnly}
                  placeholder="(Supported)"
                  hint="Text patterns to remove from extracted title"
                />
                <div>
                  <label className="block text-sm font-medium text-text-primary mb-1">
                    Case Transform
                  </label>
                  <select
                    value={config.title.case_transform}
                    onChange={(e) => updateTitle({ case_transform: e.target.value as 'none' | 'title' | 'lower' | 'upper' })}
                    disabled={isReadOnly}
                    className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                  >
                    <option value="none">None</option>
                    <option value="title">Title Case</option>
                    <option value="lower">lowercase</option>
                    <option value="upper">UPPERCASE</option>
                  </select>
                </div>
              </div>
            )}

            {/* Preview Tab */}
            {activeTab === 'preview' && (
              <div className="space-y-4">
                <ArrayInput
                  label="Preview Folders"
                  value={config.preview.folders}
                  onChange={(v) => updatePreview({ folders: v })}
                  disabled={isReadOnly}
                  placeholder="Renders"
                  hint="Exact folder names to look for preview images"
                />
                <ArrayInput
                  label="Wildcard Folders"
                  value={config.preview.wildcard_folders}
                  onChange={(v) => updatePreview({ wildcard_folders: v })}
                  disabled={isReadOnly}
                  placeholder="*Renders"
                  hint="Patterns with * wildcard (e.g., '4K Renders' matches '*Renders')"
                />
                <ArrayInput
                  label="Image Extensions"
                  value={config.preview.extensions}
                  onChange={(v) => updatePreview({ extensions: v })}
                  disabled={isReadOnly}
                  placeholder=".jpg"
                />
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-text-primary">Include Root Images</label>
                    <p className="text-xs text-text-muted">Also check for images at the design root folder</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.preview.include_root}
                      onChange={(e) => updatePreview({ include_root: e.target.checked })}
                      disabled={isReadOnly}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-bg-tertiary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent-primary peer-disabled:opacity-60"></div>
                  </label>
                </div>
              </div>
            )}

            {/* Ignore Tab */}
            {activeTab === 'ignore' && (
              <div className="space-y-4">
                <ArrayInput
                  label="Ignore Folders"
                  value={config.ignore.folders}
                  onChange={(v) => updateIgnore({ folders: v })}
                  disabled={isReadOnly}
                  placeholder="Lychee"
                  hint="Folder names to skip during import"
                />
                <ArrayInput
                  label="Ignore Extensions"
                  value={config.ignore.extensions}
                  onChange={(v) => updateIgnore({ extensions: v })}
                  disabled={isReadOnly}
                  placeholder=".gcode"
                  hint="File extensions to skip"
                />
                <ArrayInput
                  label="Ignore Patterns"
                  value={config.ignore.patterns}
                  onChange={(v) => updateIgnore({ patterns: v })}
                  disabled={isReadOnly}
                  placeholder=".DS_Store"
                  hint="Filename patterns to skip (supports * wildcard)"
                />
              </div>
            )}

            {/* Auto-Tags Tab */}
            {activeTab === 'autotag' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-text-primary">Extract from Subfolders</label>
                    <p className="text-xs text-text-muted">Use parent folder names as tags</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.auto_tags.from_subfolders}
                      onChange={(e) => updateAutoTags({ from_subfolders: e.target.checked })}
                      disabled={isReadOnly}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-bg-tertiary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent-primary peer-disabled:opacity-60"></div>
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-text-primary">Extract from Filename</label>
                    <p className="text-xs text-text-muted">Use keywords from model filenames</p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={config.auto_tags.from_filename}
                      onChange={(e) => updateAutoTags({ from_filename: e.target.checked })}
                      disabled={isReadOnly}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-bg-tertiary peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-accent-primary peer-disabled:opacity-60"></div>
                  </label>
                </div>
                {config.auto_tags.from_subfolders && (
                  <div>
                    <label className="block text-sm font-medium text-text-primary mb-1">
                      Subfolder Levels
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={config.auto_tags.subfolder_levels}
                      onChange={(e) => updateAutoTags({ subfolder_levels: parseInt(e.target.value) || 2 })}
                      disabled={isReadOnly}
                      className="w-full px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary disabled:opacity-60 focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
                    />
                    <p className="text-xs text-text-muted mt-1">Number of parent folder levels to use for tags</p>
                  </div>
                )}
                <ArrayInput
                  label="Strip Patterns (Regex)"
                  value={config.auto_tags.strip_patterns}
                  onChange={(v) => updateAutoTags({ strip_patterns: v })}
                  disabled={isReadOnly}
                  placeholder="Tier$"
                  hint="Regex patterns to remove from folder names before using as tags"
                />
              </div>
            )}
          </div>

          {/* Error message */}
          {error && (
            <div className="mx-4 mb-4 px-3 py-2 bg-accent-danger/20 border border-accent-danger/50 rounded text-sm text-accent-danger">
              {error}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-4 border-t border-bg-tertiary flex-shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
            >
              {isReadOnly ? 'Close' : 'Cancel'}
            </button>
            {!isReadOnly && (
              <button
                type="submit"
                disabled={isSaving || !name.trim()}
                className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isSaving && <SpinnerIcon className="w-4 h-4 animate-spin" />}
                {isSaving ? 'Saving...' : mode === 'create' ? 'Create' : 'Save'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}

// =============================================================================
// Helper Components
// =============================================================================

interface ArrayInputProps {
  label: string
  value: string[]
  onChange: (value: string[]) => void
  disabled?: boolean
  placeholder?: string
  hint?: string
}

function ArrayInput({ label, value, onChange, disabled, placeholder, hint }: ArrayInputProps) {
  const [inputValue, setInputValue] = useState('')

  const handleAdd = () => {
    const trimmed = inputValue.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
      setInputValue('')
    }
  }

  const handleRemove = (item: string) => {
    onChange(value.filter((v) => v !== item))
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAdd()
    }
  }

  return (
    <div>
      <label className="block text-sm font-medium text-text-primary mb-1">{label}</label>
      {!disabled && (
        <div className="flex gap-2 mb-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="flex-1 px-3 py-2 bg-bg-tertiary border border-bg-tertiary rounded-lg text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent-primary/50"
          />
          <button
            type="button"
            onClick={handleAdd}
            disabled={!inputValue.trim()}
            className="px-3 py-2 bg-bg-tertiary text-text-secondary hover:text-text-primary rounded-lg transition-colors disabled:opacity-50"
          >
            Add
          </button>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {value.map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-1 px-2 py-1 bg-bg-tertiary rounded text-sm text-text-primary"
          >
            <code className="text-xs">{item}</code>
            {!disabled && (
              <button
                type="button"
                onClick={() => handleRemove(item)}
                className="text-text-muted hover:text-accent-danger transition-colors"
              >
                <CloseIcon className="w-3 h-3" />
              </button>
            )}
          </span>
        ))}
        {value.length === 0 && <span className="text-sm text-text-muted italic">None configured</span>}
      </div>
      {hint && <p className="text-xs text-text-muted mt-1">{hint}</p>}
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" strokeWidth={2} strokeDasharray="60" strokeDashoffset="20" />
    </svg>
  )
}
