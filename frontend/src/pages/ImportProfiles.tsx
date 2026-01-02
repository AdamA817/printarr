/**
 * Import Profiles management page (v0.8)
 * Allows viewing and editing import profile configurations
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useImportProfiles,
  useCreateImportProfile,
  useDeleteImportProfile,
  useImportProfileUsage,
} from '@/hooks/useImportProfiles'
import {
  ImportProfileCard,
  ImportProfileCardSkeleton,
  ProfileEditorModal,
} from '@/components/import-sources'
import type { ImportProfile, ImportProfileCreate } from '@/types/import-source'

type EditorMode = 'view' | 'edit' | 'create' | 'duplicate'

export function ImportProfiles() {
  const [editorState, setEditorState] = useState<{
    isOpen: boolean
    mode: EditorMode
    profile: ImportProfile | null
  }>({
    isOpen: false,
    mode: 'view',
    profile: null,
  })
  const [deleteTarget, setDeleteTarget] = useState<ImportProfile | null>(null)

  const { data, isLoading, error } = useImportProfiles()
  const createProfile = useCreateImportProfile()
  const deleteProfile = useDeleteImportProfile()

  const openEditor = (mode: EditorMode, profile: ImportProfile | null = null) => {
    setEditorState({ isOpen: true, mode, profile })
  }

  const closeEditor = () => {
    setEditorState({ isOpen: false, mode: 'view', profile: null })
    createProfile.reset()
  }

  const handleSave = (formData: ImportProfileCreate) => {
    if (editorState.mode === 'edit' && editorState.profile) {
      // For edit mode, we'd need updateProfile mutation
      // For now, creating new works for create/duplicate
      createProfile.mutate(formData, {
        onSuccess: closeEditor,
      })
    } else {
      createProfile.mutate(formData, {
        onSuccess: closeEditor,
      })
    }
  }

  const handleDelete = () => {
    if (!deleteTarget) return
    deleteProfile.mutate(deleteTarget.id, {
      onSuccess: () => setDeleteTarget(null),
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <Link
            to="/import-sources"
            className="text-sm text-text-secondary hover:text-accent-primary transition-colors flex items-center gap-1 mb-1"
          >
            <ArrowLeftIcon className="w-4 h-4" />
            <span>Back to Sources</span>
          </Link>
          <h1 className="text-xl font-bold text-text-primary">Import Profiles</h1>
          {data && (
            <p className="text-sm text-text-secondary mt-1">
              {data.total} profile{data.total !== 1 ? 's' : ''} available
            </p>
          )}
        </div>
        <button
          onClick={() => openEditor('create')}
          className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors flex items-center gap-2"
        >
          <PlusIcon className="w-5 h-5" />
          <span>New Profile</span>
        </button>
      </div>

      {/* Info card */}
      <div className="bg-bg-secondary rounded-lg p-4 text-sm text-text-secondary">
        <p>
          Import profiles define how Printarr detects and organizes designs from folders.
          Built-in profiles cannot be edited but can be duplicated.
        </p>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          <ImportProfileCardSkeleton />
          <ImportProfileCardSkeleton />
          <ImportProfileCardSkeleton />
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-4">
          <p className="text-accent-danger">
            Failed to load import profiles: {(error as Error).message}
          </p>
        </div>
      )}

      {/* Profile list */}
      {data && data.items.length > 0 && (
        <div className="space-y-3">
          {/* Built-in profiles first */}
          {data.items
            .filter((p) => p.is_builtin)
            .map((profile) => (
              <ProfileCardWithUsage
                key={profile.id}
                profile={profile}
                onView={() => openEditor('view', profile)}
                onEdit={() => openEditor('edit', profile)}
                onDuplicate={() => openEditor('duplicate', profile)}
                onDelete={() => setDeleteTarget(profile)}
                isDeleting={deleteProfile.isPending && deleteTarget?.id === profile.id}
              />
            ))}

          {/* Custom profiles */}
          {data.items.filter((p) => !p.is_builtin).length > 0 && (
            <>
              <div className="text-sm text-text-muted pt-2">Custom Profiles</div>
              {data.items
                .filter((p) => !p.is_builtin)
                .map((profile) => (
                  <ProfileCardWithUsage
                    key={profile.id}
                    profile={profile}
                    onView={() => openEditor('view', profile)}
                    onEdit={() => openEditor('edit', profile)}
                    onDuplicate={() => openEditor('duplicate', profile)}
                    onDelete={() => setDeleteTarget(profile)}
                    isDeleting={deleteProfile.isPending && deleteTarget?.id === profile.id}
                  />
                ))}
            </>
          )}
        </div>
      )}

      {/* Editor modal */}
      <ProfileEditorModal
        isOpen={editorState.isOpen}
        profile={editorState.profile}
        mode={editorState.mode}
        onClose={closeEditor}
        onSave={handleSave}
        isSaving={createProfile.isPending}
        error={
          createProfile.error
            ? (createProfile.error as Error).message || 'Failed to save profile'
            : null
        }
      />

      {/* Delete confirmation */}
      {deleteTarget && (
        <DeleteConfirmModal
          profileName={deleteTarget.name}
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={deleteProfile.isPending}
        />
      )}
    </div>
  )
}

// =============================================================================
// Helper Components
// =============================================================================

interface ProfileCardWithUsageProps {
  profile: ImportProfile
  onView: () => void
  onEdit: () => void
  onDuplicate: () => void
  onDelete: () => void
  isDeleting: boolean
}

function ProfileCardWithUsage({
  profile,
  onView,
  onEdit,
  onDuplicate,
  onDelete,
  isDeleting,
}: ProfileCardWithUsageProps) {
  const { data: usage } = useImportProfileUsage(profile.id)

  return (
    <ImportProfileCard
      profile={profile}
      usageCount={usage?.sources_using ?? 0}
      onView={onView}
      onEdit={onEdit}
      onDuplicate={onDuplicate}
      onDelete={onDelete}
      isDeleting={isDeleting}
    />
  )
}

interface DeleteConfirmModalProps {
  profileName: string
  onConfirm: () => void
  onCancel: () => void
  isDeleting: boolean
}

function DeleteConfirmModal({ profileName, onConfirm, onCancel, isDeleting }: DeleteConfirmModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-2">Delete Profile</h3>
        <p className="text-text-secondary mb-4">
          Are you sure you want to delete <span className="font-medium text-text-primary">{profileName}</span>?
          This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
          >
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
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

function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
    </svg>
  )
}
