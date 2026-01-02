/**
 * Google Drive connection card for OAuth flow
 * Shows connection status and allows initiating/managing OAuth connections
 */
import { useState, useEffect } from 'react'
import {
  useGoogleOAuthStatus,
  useGoogleCredentials,
  useInitiateGoogleOAuth,
  useRevokeGoogleCredentials,
} from '@/hooks/useGoogleOAuth'

interface GoogleConnectCardProps {
  onConnected?: (credentialsId: string) => void
  selectedCredentialsId?: string
  onSelectCredentials?: (id: string | null) => void
}

export function GoogleConnectCard({
  onConnected,
  selectedCredentialsId,
  onSelectCredentials,
}: GoogleConnectCardProps) {
  const { data: status, isLoading: statusLoading } = useGoogleOAuthStatus()
  const { data: credentials, isLoading: credentialsLoading } = useGoogleCredentials()
  const initiateOAuth = useInitiateGoogleOAuth()
  const revokeCredentials = useRevokeGoogleCredentials()
  const [revokeTarget, setRevokeTarget] = useState<string | null>(null)

  // Store the state in localStorage for OAuth callback verification
  const handleConnect = async () => {
    try {
      const result = await initiateOAuth.mutateAsync()
      // Store state for callback verification
      localStorage.setItem('google_oauth_state', result.state)
      // Redirect to Google
      window.location.href = result.authorization_url
    } catch (error) {
      console.error('Failed to initiate OAuth:', error)
    }
  }

  const handleRevoke = async (id: string) => {
    try {
      await revokeCredentials.mutateAsync(id)
      setRevokeTarget(null)
      if (selectedCredentialsId === id && onSelectCredentials) {
        onSelectCredentials(null)
      }
    } catch (error) {
      console.error('Failed to revoke credentials:', error)
    }
  }

  // Auto-select first credentials if none selected
  useEffect(() => {
    if (credentials?.items.length && !selectedCredentialsId && onSelectCredentials) {
      onSelectCredentials(credentials.items[0].id)
    }
  }, [credentials, selectedCredentialsId, onSelectCredentials])

  // Notify when connected
  useEffect(() => {
    if (selectedCredentialsId && onConnected) {
      onConnected(selectedCredentialsId)
    }
  }, [selectedCredentialsId, onConnected])

  const isLoading = statusLoading || credentialsLoading

  if (isLoading) {
    return (
      <div className="bg-bg-tertiary rounded-lg p-4 animate-pulse">
        <div className="h-6 w-48 bg-bg-secondary rounded mb-2" />
        <div className="h-4 w-32 bg-bg-secondary rounded" />
      </div>
    )
  }

  // Not configured - show setup message
  if (!status?.configured) {
    return (
      <div className="bg-bg-tertiary rounded-lg p-4">
        <div className="flex items-start gap-3">
          <GoogleDriveIcon className="w-8 h-8 text-text-muted flex-shrink-0" />
          <div>
            <h3 className="font-medium text-text-primary">Google Drive Not Configured</h3>
            <p className="text-sm text-text-muted mt-1">
              Google OAuth credentials need to be configured in the backend settings.
              Set <code className="text-accent-primary">GOOGLE_CLIENT_ID</code> and{' '}
              <code className="text-accent-primary">GOOGLE_CLIENT_SECRET</code> environment variables.
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Configured - show connect button or connected accounts
  return (
    <div className="bg-bg-tertiary rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GoogleDriveIcon className="w-8 h-8 text-[#4285f4]" />
          <div>
            <h3 className="font-medium text-text-primary">Google Drive</h3>
            <p className="text-sm text-text-muted">
              {credentials?.items.length
                ? `${credentials.items.length} account${credentials.items.length !== 1 ? 's' : ''} connected`
                : 'No accounts connected'}
            </p>
          </div>
        </div>
        <button
          onClick={handleConnect}
          disabled={initiateOAuth.isPending}
          className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {initiateOAuth.isPending ? (
            <>
              <SpinnerIcon className="w-4 h-4 animate-spin" />
              <span>Connecting...</span>
            </>
          ) : (
            <>
              <PlusIcon className="w-4 h-4" />
              <span>Connect Account</span>
            </>
          )}
        </button>
      </div>

      {initiateOAuth.error && (
        <div className="bg-accent-danger/20 border border-accent-danger/50 rounded-lg p-3 text-sm text-accent-danger">
          Failed to start Google authentication. Please try again.
        </div>
      )}

      {/* Connected accounts */}
      {credentials && credentials.items.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-text-muted">Select an account to use:</p>
          {credentials.items.map((cred) => (
            <div
              key={cred.id}
              className={`flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer ${
                selectedCredentialsId === cred.id
                  ? 'border-accent-primary bg-accent-primary/10'
                  : 'border-bg-tertiary bg-bg-secondary hover:border-text-muted'
              }`}
              onClick={() => onSelectCredentials?.(cred.id)}
            >
              <div className="flex items-center gap-3">
                <input
                  type="radio"
                  checked={selectedCredentialsId === cred.id}
                  onChange={() => onSelectCredentials?.(cred.id)}
                  className="text-accent-primary"
                />
                <div>
                  <p className="text-sm text-text-primary font-medium">{cred.email}</p>
                  <p className="text-xs text-text-muted">
                    Connected {new Date(cred.created_at).toLocaleDateString()}
                    {cred.expires_at && (
                      <>
                        {' · '}
                        {new Date(cred.expires_at) < new Date() ? (
                          <span className="text-accent-warning">Token expired</span>
                        ) : (
                          `Expires ${new Date(cred.expires_at).toLocaleDateString()}`
                        )}
                      </>
                    )}
                  </p>
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setRevokeTarget(cred.id)
                }}
                className="p-2 text-text-muted hover:text-accent-danger transition-colors"
                title="Disconnect account"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Revoke confirmation */}
      {revokeTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setRevokeTarget(null)} />
          <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-text-primary mb-2">Disconnect Account</h3>
            <p className="text-text-secondary mb-4">
              Are you sure you want to disconnect this Google account? Import sources using this
              account will stop working until reconnected.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setRevokeTarget(null)}
                disabled={revokeCredentials.isPending}
                className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleRevoke(revokeTarget)}
                disabled={revokeCredentials.isPending}
                className="px-4 py-2 bg-accent-danger text-white rounded-lg hover:bg-accent-danger/80 transition-colors disabled:opacity-50"
              >
                {revokeCredentials.isPending ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function GoogleDriveIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M7.71 3.5L1.15 15l4.58 7.5h13.54l4.58-7.5L17.29 3.5H7.71zm.79 1.5h7l5 8.5H3.5l5-8.5zm.5 9h7l-3.5 6h-7l3.5-6z" />
    </svg>
  )
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
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

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}
