/**
 * Import Sources management page (v0.8)
 * Allows managing Google Drive, bulk folders, and upload import sources
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useImportSources,
  useCreateImportSource,
  useDeleteImportSource,
  useTriggerSync,
} from '@/hooks/useImportSources'
import {
  ImportSourceCard,
  ImportSourceCardSkeleton,
  AddImportSourceModal,
  DeleteSourceModal,
  UploadModal,
  ImportHistoryModal,
} from '@/components/import-sources'
import type { ImportSource, ImportSourceCreate } from '@/types/import-source'

export function ImportSources() {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ImportSource | null>(null)
  const [historyTarget, setHistoryTarget] = useState<ImportSource | null>(null)

  const { data, isLoading, error } = useImportSources()
  const createSource = useCreateImportSource()
  const deleteSource = useDeleteImportSource()
  const triggerSync = useTriggerSync()

  const handleAddSource = (formData: ImportSourceCreate) => {
    createSource.mutate(formData, {
      onSuccess: (newSource) => {
        setIsAddModalOpen(false)
        createSource.reset()

        // Auto-trigger sync for bulk folder sources
        if (newSource.source_type === 'BULK_FOLDER' || newSource.source_type === 'GOOGLE_DRIVE') {
          triggerSync.mutate({
            id: newSource.id,
            request: { auto_import: true },
          })
        }
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

  const handleViewHistory = (id: string) => {
    const source = data?.items.find((s) => s.id === id)
    if (source) {
      setHistoryTarget(source)
    }
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
        <div className="flex items-center gap-3">
          <Link
            to="/import-profiles"
            className="px-4 py-2 text-text-secondary hover:text-text-primary hover:bg-bg-tertiary rounded-lg transition-colors flex items-center gap-2"
          >
            <CogIcon className="w-5 h-5" />
            <span>Profiles</span>
          </Link>
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="px-4 py-2 bg-bg-tertiary text-text-primary hover:bg-bg-tertiary/80 rounded-lg transition-colors flex items-center gap-2"
          >
            <UploadIcon className="w-5 h-5" />
            <span>Upload</span>
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors flex items-center gap-2"
          >
            <PlusIcon className="w-5 h-5" />
            <span>Add Source</span>
          </button>
        </div>
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

      {/* Upload modal */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
      />

      {/* History modal */}
      <ImportHistoryModal
        isOpen={!!historyTarget}
        source={historyTarget}
        onClose={() => setHistoryTarget(null)}
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

function CogIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
      />
    </svg>
  )
}
