/**
 * AI Analysis Settings Component (DEC-043)
 *
 * Settings panel for configuring AI-powered design analysis features.
 */

import { useState, useEffect } from 'react'
import { useAiSettings, useUpdateAiSettings } from '@/hooks/useAi'

// Available AI models
const AI_MODELS = [
  { value: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash (Recommended)' },
  { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
  { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
]

export function AiSettings() {
  const { data: settings, isLoading } = useAiSettings()
  const updateSettings = useUpdateAiSettings()

  // Local state for form
  const [enabled, setEnabled] = useState(false)
  const [model, setModel] = useState('gemini-2.0-flash')
  const [autoAnalyze, setAutoAnalyze] = useState(false)
  const [selectBestPreview, setSelectBestPreview] = useState(false)
  const [rateLimitRpm, setRateLimitRpm] = useState(15)
  const [maxTags, setMaxTags] = useState(20)
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle')

  // Initialize form with loaded settings
  useEffect(() => {
    if (settings) {
      setEnabled(settings.enabled)
      setModel(settings.model)
      setAutoAnalyze(settings.auto_analyze_on_import)
      setSelectBestPreview(settings.select_best_preview)
      setRateLimitRpm(settings.rate_limit_rpm)
      setMaxTags(settings.max_tags_per_design)
    }
  }, [settings])

  // Track changes
  useEffect(() => {
    if (!settings) return
    setHasChanges(
      enabled !== settings.enabled ||
      model !== settings.model ||
      autoAnalyze !== settings.auto_analyze_on_import ||
      selectBestPreview !== settings.select_best_preview ||
      rateLimitRpm !== settings.rate_limit_rpm ||
      maxTags !== settings.max_tags_per_design
    )
  }, [enabled, model, autoAnalyze, selectBestPreview, rateLimitRpm, maxTags, settings])

  // Validation
  const rpmError = rateLimitRpm < 5 || rateLimitRpm > 60 ? 'Must be between 5 and 60' : null
  const tagsError = maxTags < 1 || maxTags > 30 ? 'Must be between 1 and 30' : null

  const handleSave = async () => {
    if (rpmError || tagsError) return

    setSaveStatus('saving')
    try {
      await updateSettings.mutateAsync({
        enabled,
        model,
        auto_analyze_on_import: autoAnalyze,
        select_best_preview: selectBestPreview,
        rate_limit_rpm: rateLimitRpm,
        max_tags_per_design: maxTags,
      })
      setSaveStatus('success')
      setHasChanges(false)
      setTimeout(() => setSaveStatus('idle'), 2000)
    } catch (error) {
      console.error('Failed to save AI settings:', error)
      setSaveStatus('error')
      setTimeout(() => setSaveStatus('idle'), 3000)
    }
  }

  if (isLoading) {
    return <SettingsSkeleton />
  }

  const apiConfigured = settings?.api_key_configured ?? false

  return (
    <div className="bg-bg-secondary rounded-lg p-6">
      <div className="flex items-center gap-3 mb-4">
        <SparklesIcon className="w-6 h-6 text-purple-400" />
        <h3 className="text-lg font-semibold text-text-primary">
          AI Analysis
        </h3>
        {!apiConfigured && (
          <span className="text-xs px-2 py-0.5 rounded bg-accent-warning/20 text-accent-warning">
            Not Configured
          </span>
        )}
      </div>

      {/* API Key Status */}
      {!apiConfigured && (
        <div className="mb-6 p-4 bg-accent-warning/10 rounded-lg border border-accent-warning/30">
          <p className="text-sm text-text-primary mb-2">
            <strong>API Key Required</strong>
          </p>
          <p className="text-sm text-text-secondary">
            To use AI features, set the <code className="px-1 py-0.5 bg-bg-tertiary rounded text-accent-primary">PRINTARR_AI_API_KEY</code> environment variable
            with your Google Gemini API key.
          </p>
        </div>
      )}

      <div className="space-y-6">
        {/* Enable AI Toggle */}
        <div className="flex items-start justify-between">
          <div>
            <label
              htmlFor="ai-enabled"
              className="block text-sm font-medium text-text-primary mb-1"
            >
              Enable AI Features
            </label>
            <p className="text-sm text-text-secondary">
              Enable AI-powered design analysis using Google Gemini.
            </p>
          </div>
          <button
            id="ai-enabled"
            role="switch"
            aria-checked={enabled}
            onClick={() => setEnabled(!enabled)}
            disabled={!apiConfigured}
            className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-secondary disabled:opacity-50 disabled:cursor-not-allowed ${
              enabled ? 'bg-accent-primary' : 'bg-bg-tertiary'
            }`}
          >
            <span
              className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                enabled ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        {enabled && (
          <>
            {/* Model Selection */}
            <div>
              <label
                htmlFor="ai-model"
                className="block text-sm font-medium text-text-primary mb-2"
              >
                AI Model
              </label>
              <select
                id="ai-model"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full max-w-md px-3 py-2 rounded bg-bg-tertiary text-text-primary border border-transparent focus:outline-none focus:ring-2 focus:ring-accent-primary"
              >
                {AI_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Auto-analyze Toggle */}
            <div className="flex items-start justify-between">
              <div>
                <label
                  htmlFor="auto-analyze"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  Auto-Analyze on Import
                </label>
                <p className="text-sm text-text-secondary">
                  Automatically analyze new designs when they are imported.
                </p>
              </div>
              <button
                id="auto-analyze"
                role="switch"
                aria-checked={autoAnalyze}
                onClick={() => setAutoAnalyze(!autoAnalyze)}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-secondary ${
                  autoAnalyze ? 'bg-accent-primary' : 'bg-bg-tertiary'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    autoAnalyze ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Select Best Preview Toggle */}
            <div className="flex items-start justify-between">
              <div>
                <label
                  htmlFor="best-preview"
                  className="block text-sm font-medium text-text-primary mb-1"
                >
                  AI Selects Best Preview
                </label>
                <p className="text-sm text-text-secondary">
                  Let AI pick the best preview image when multiple are available.
                </p>
              </div>
              <button
                id="best-preview"
                role="switch"
                aria-checked={selectBestPreview}
                onClick={() => setSelectBestPreview(!selectBestPreview)}
                className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-secondary ${
                  selectBestPreview ? 'bg-accent-primary' : 'bg-bg-tertiary'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                    selectBestPreview ? 'translate-x-5' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Advanced Settings */}
            <div className="border-t border-bg-tertiary pt-6">
              <h4 className="text-sm font-medium text-text-secondary mb-4">Advanced Settings</h4>

              {/* Rate Limit */}
              <div className="mb-6">
                <label
                  htmlFor="rate-limit"
                  className="block text-sm font-medium text-text-primary mb-2"
                >
                  Rate Limit (requests per minute)
                </label>
                <p className="text-sm text-text-secondary mb-3">
                  Maximum number of AI requests per minute. Lower values prevent API throttling.
                </p>
                <div className="flex items-center gap-4">
                  <input
                    id="rate-limit"
                    type="range"
                    min={5}
                    max={60}
                    step={5}
                    value={rateLimitRpm}
                    onChange={(e) => setRateLimitRpm(Number(e.target.value))}
                    className="flex-1 max-w-xs h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
                  />
                  <span className="w-12 text-right text-sm text-text-primary font-mono">{rateLimitRpm}</span>
                </div>
                {rpmError && (
                  <p className="mt-2 text-sm text-accent-danger">{rpmError}</p>
                )}
              </div>

              {/* Max Tags */}
              <div>
                <label
                  htmlFor="max-tags"
                  className="block text-sm font-medium text-text-primary mb-2"
                >
                  Maximum Tags per Design
                </label>
                <p className="text-sm text-text-secondary mb-3">
                  Maximum number of tags AI can generate per design.
                </p>
                <div className="flex items-center gap-4">
                  <input
                    id="max-tags"
                    type="range"
                    min={1}
                    max={30}
                    step={1}
                    value={maxTags}
                    onChange={(e) => setMaxTags(Number(e.target.value))}
                    className="flex-1 max-w-xs h-2 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-accent-primary"
                  />
                  <span className="w-12 text-right text-sm text-text-primary font-mono">{maxTags}</span>
                </div>
                {tagsError && (
                  <p className="mt-2 text-sm text-accent-danger">{tagsError}</p>
                )}
              </div>
            </div>
          </>
        )}

        {/* Save Button */}
        {hasChanges && (
          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={!!rpmError || !!tagsError || saveStatus === 'saving'}
              className="px-4 py-2 rounded bg-accent-primary text-white font-medium hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saveStatus === 'saving' ? 'Saving...' : 'Save Changes'}
            </button>
            {saveStatus === 'success' && (
              <span className="text-sm text-accent-success flex items-center gap-1">
                <CheckIcon className="w-4 h-4" />
                Saved
              </span>
            )}
            {saveStatus === 'error' && (
              <span className="text-sm text-accent-danger">
                Failed to save. Please try again.
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
      />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  )
}

function SettingsSkeleton() {
  return (
    <div className="bg-bg-secondary rounded-lg p-6 animate-pulse">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-6 h-6 bg-bg-tertiary rounded" />
        <div className="h-6 bg-bg-tertiary rounded w-32" />
      </div>
      <div className="space-y-6">
        {[...Array(4)].map((_, i) => (
          <div key={i}>
            <div className="h-4 bg-bg-tertiary rounded w-40 mb-2" />
            <div className="h-4 bg-bg-tertiary rounded w-3/4 mb-3" />
            <div className="h-8 bg-bg-tertiary rounded w-full" />
          </div>
        ))}
      </div>
    </div>
  )
}
