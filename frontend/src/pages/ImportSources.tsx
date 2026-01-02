/**
 * Import Sources management page (v0.8)
 * Allows managing Google Drive, bulk folders, and upload import sources
 */
import { useState } from 'react'
import {
  useImportSources,
  useCreateImportSource,
  useDeleteImportSource,
} from '@/hooks/useImportSources'
import {
  ImportSourceCard,
  ImportSourceCardSkeleton,
  AddImportSourceModal,
  DeleteSourceModal,
} from '@/components/import-sources'
import type { ImportSource, ImportSourceCreate } from '@/types/import-source'

export function ImportSources() {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ImportSource | null>(null)

  const { data, isLoading, error } = useImportSources()
  const createSource = useCreateImportSource()
  const deleteSource = useDeleteImportSource()

  const handleAddSource = (formData: ImportSourceCreate) => {
    createSource.mutate(formData, {
      onSuccess: () => {
        setIsAddModalOpen(false)
        createSource.reset()
      },
    })
  }

  const handleDeleteClick = (id: string) => {
    const source = data?.items.find((s) => s.id === id)
    if (source) {
      setDeleteTarget(source)
    }
  }

  const handleDeleteConfirm = (keepDesigns: boolean) => {
    if (!deleteTarget) return

    deleteSource.mutate(
      { id: deleteTarget.id, keepDesigns },
      {
        onSuccess: () => {
          setDeleteTarget(null)
        },
      }
    )
  }

  const handleEdit = (_source: ImportSource) => {
    // TODO: Implement edit modal (future enhancement)
    // For now, edit functionality will be part of a separate issue
  }

  const handleViewHistory = (_id: string) => {
    // TODO: Navigate to history page or open history modal
    // This will be implemented as part of issue #149
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Import Sources</h1>
          {data && (
            <p className="text-sm text-text-secondary mt-1">
              {data.total} source{data.total !== 1 ? 's' : ''} configured
            </p>
          )}
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors flex items-center gap-2"
        >
          <PlusIcon className="w-5 h-5" />
          <span>Add Source</span>
        </button>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          <ImportSourceCardSkeleton />
          <ImportSourceCardSkeleton />
          <ImportSourceCardSkeleton />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load import sources: {(error as Error).message}
          </p>
        </div>
      )}

      {/* Empty state */}
      {data && data.items.length === 0 && (
        <div className="bg-bg-secondary rounded-lg p-8 text-center">
          <div className="text-4xl mb-4">📁</div>
          <h3 className="text-lg font-medium text-text-primary mb-2">
            No import sources yet
          </h3>
          <p className="text-text-secondary mb-4 max-w-md mx-auto">
            Add an import source to bring in designs from Google Drive, local folders, or direct uploads.
          </p>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors"
          >
            Add Your First Source
          </button>
        </div>
      )}

      {/* Source list */}
      {data && data.items.length > 0 && (
        <div className="space-y-3">
          {data.items.map((source) => (
            <ImportSourceCard
              key={source.id}
              source={source}
              onEdit={handleEdit}
              onDelete={handleDeleteClick}
              onViewHistory={handleViewHistory}
              isDeleting={deleteSource.isPending && deleteTarget?.id === source.id}
            />
          ))}
        </div>
      )}

      {/* Add source modal */}
      <AddImportSourceModal
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false)
          createSource.reset()
        }}
        onSubmit={handleAddSource}
        isSubmitting={createSource.isPending}
        error={
          createSource.error
            ? (createSource.error as Error).message || 'Failed to create import source'
            : null
        }
      />

      {/* Delete confirmation modal */}
      <DeleteSourceModal
        isOpen={!!deleteTarget}
        sourceName={deleteTarget?.name || ''}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        isDeleting={deleteSource.isPending}
      />
    </div>
  )
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  )
}
