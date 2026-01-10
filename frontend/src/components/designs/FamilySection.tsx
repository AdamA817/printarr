import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useFamily,
  useRemoveDesignFromFamily,
  useDetectFamilyForDesign,
} from '@/hooks/useFamilies'

interface FamilySectionProps {
  designId: string
  familyId: string | null
  variantName: string | null
}

export function FamilySection({ designId, familyId, variantName }: FamilySectionProps) {
  const { data: family, isLoading } = useFamily(familyId || undefined)
  const removeMutation = useRemoveDesignFromFamily()
  const detectMutation = useDetectFamilyForDesign()
  const [showRemoveConfirm, setShowRemoveConfirm] = useState(false)
  const [showDetecting, setShowDetecting] = useState(false)

  const handleRemove = async () => {
    if (!familyId) return
    try {
      await removeMutation.mutateAsync({ familyId, designId })
      setShowRemoveConfirm(false)
    } catch (err) {
      console.error('Failed to remove from family:', err)
    }
  }

  const handleDetect = async () => {
    setShowDetecting(true)
    try {
      const result = await detectMutation.mutateAsync(designId)
      if (result.family_id) {
        // Family was found or created - the hook will invalidate queries
      }
    } catch (err) {
      console.error('Failed to detect family:', err)
    } finally {
      setShowDetecting(false)
    }
  }

  // Design is not in a family - show detect option
  if (!familyId) {
    return (
      <section className="bg-bg-secondary rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <FamilyIcon className="w-5 h-5 text-purple-400" />
          <h3 className="text-sm font-medium text-text-muted">Design Family</h3>
        </div>
        <p className="text-sm text-text-secondary mb-3">
          This design is not part of a family. Group related designs (variants, remixes, etc.) together.
        </p>

        {detectMutation.isSuccess && !detectMutation.data?.family_id && (
          <p className="text-xs text-text-muted mb-3">
            No matching family patterns found.
          </p>
        )}

        {detectMutation.isSuccess && detectMutation.data?.family_id && (
          <p className="text-xs text-accent-success mb-3">
            Added to family: {detectMutation.data.family_name}
          </p>
        )}

        {detectMutation.isError && (
          <p className="text-xs text-accent-danger mb-3">
            Failed to detect family.
          </p>
        )}

        <button
          onClick={handleDetect}
          disabled={detectMutation.isPending || showDetecting}
          className="w-full px-3 py-2 text-sm rounded bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          <FamilyIcon className="w-4 h-4" />
          {detectMutation.isPending ? 'Detecting...' : 'Auto-Detect Family'}
        </button>
      </section>
    )
  }

  // Loading family data
  if (isLoading) {
    return (
      <section className="bg-bg-secondary rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <FamilyIcon className="w-5 h-5 text-purple-400" />
          <h3 className="text-sm font-medium text-text-muted">Design Family</h3>
        </div>
        <div className="animate-pulse space-y-2">
          <div className="h-4 bg-bg-tertiary rounded w-3/4" />
          <div className="h-4 bg-bg-tertiary rounded w-1/2" />
        </div>
      </section>
    )
  }

  // Family not found (shouldn't happen in normal use)
  if (!family) {
    return null
  }

  // Get other variants (excluding current design)
  const otherVariants = family.designs.filter((d) => d.id !== designId)

  return (
    <section className="bg-bg-secondary rounded-lg p-4">
      <div className="flex items-center gap-2 mb-3">
        <FamilyIcon className="w-5 h-5 text-purple-400" />
        <h3 className="text-sm font-medium text-text-muted">Design Family</h3>
      </div>

      {/* Family Header */}
      <div className="mb-4">
        <Link
          to={`/families/${family.id}`}
          className="text-sm font-medium text-text-primary hover:text-accent-primary transition-colors"
        >
          {family.display_name}
        </Link>
        <p className="text-xs text-text-muted mt-0.5">
          by {family.display_designer}
        </p>
        {variantName && (
          <div className="mt-2">
            <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
              Variant: {variantName}
            </span>
          </div>
        )}
      </div>

      {/* Other Variants */}
      {otherVariants.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-medium text-text-muted mb-2">
            Other Variants ({otherVariants.length})
          </h4>
          <div className="space-y-1.5 max-h-32 overflow-y-auto">
            {otherVariants.slice(0, 5).map((variant) => (
              <Link
                key={variant.id}
                to={`/designs/${variant.id}`}
                className="block text-xs text-text-secondary hover:text-accent-primary transition-colors truncate"
              >
                {variant.variant_name ? (
                  <span>
                    <span className="text-purple-400">{variant.variant_name}</span>
                    {' - '}
                    {variant.canonical_title}
                  </span>
                ) : (
                  variant.canonical_title
                )}
              </Link>
            ))}
            {otherVariants.length > 5 && (
              <Link
                to={`/families/${family.id}`}
                className="block text-xs text-accent-primary hover:underline"
              >
                +{otherVariants.length - 5} more...
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="space-y-2">
        <Link
          to={`/families/${family.id}`}
          className="block w-full px-3 py-2 text-sm rounded bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 transition-colors text-center"
        >
          View Family Details
        </Link>

        {showRemoveConfirm ? (
          <div className="p-2 bg-bg-tertiary rounded space-y-2">
            <p className="text-xs text-text-muted">
              Remove this design from the family?
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleRemove}
                disabled={removeMutation.isPending}
                className="flex-1 px-2 py-1.5 text-xs rounded bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30 transition-colors disabled:opacity-50"
              >
                {removeMutation.isPending ? 'Removing...' : 'Remove'}
              </button>
              <button
                onClick={() => setShowRemoveConfirm(false)}
                className="flex-1 px-2 py-1.5 text-xs rounded bg-bg-secondary text-text-muted hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowRemoveConfirm(true)}
            className="w-full px-3 py-2 text-xs rounded bg-bg-tertiary text-text-muted hover:text-text-secondary hover:bg-bg-tertiary/80 transition-colors"
          >
            Remove from Family
          </button>
        )}
      </div>
    </section>
  )
}

function FamilyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
    </svg>
  )
}
