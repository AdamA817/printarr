/**
 * Google OAuth callback handler page
 * Processes the OAuth callback from Google and stores credentials
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useGoogleOAuthCallback } from '@/hooks/useGoogleOAuth'

type CallbackState = 'processing' | 'success' | 'error'

export function GoogleOAuthCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const oauthCallback = useGoogleOAuthCallback()
  const [state, setState] = useState<CallbackState>('processing')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [email, setEmail] = useState<string | null>(null)

  useEffect(() => {
    const processCallback = async () => {
      const code = searchParams.get('code')
      const returnedState = searchParams.get('state')
      const error = searchParams.get('error')

      // Check for error from Google
      if (error) {
        setErrorMessage(
          error === 'access_denied'
            ? 'Access was denied. You may have cancelled the authorization.'
            : `Google returned an error: ${error}`
        )
        setState('error')
        return
      }

      // Validate required parameters
      if (!code || !returnedState) {
        setErrorMessage('Missing required OAuth parameters. Please try again.')
        setState('error')
        return
      }

      // Verify state matches what we stored
      const storedState = localStorage.getItem('google_oauth_state')
      if (storedState !== returnedState) {
        setErrorMessage('OAuth state mismatch. This could be a security issue. Please try again.')
        setState('error')
        localStorage.removeItem('google_oauth_state')
        return
      }

      // Clear stored state
      localStorage.removeItem('google_oauth_state')

      // Exchange code for credentials
      try {
        const result = await oauthCallback.mutateAsync({
          code,
          state: returnedState,
        })

        if (result.success) {
          setEmail(result.email)
          setState('success')
          // Redirect after a short delay
          setTimeout(() => {
            navigate('/import-sources', { replace: true })
          }, 2000)
        } else {
          setErrorMessage(result.message || 'Failed to complete authentication')
          setState('error')
        }
      } catch (err) {
        setErrorMessage(
          err instanceof Error ? err.message : 'An unexpected error occurred'
        )
        setState('error')
      }
    }

    processCallback()
  }, [searchParams, oauthCallback, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary p-4">
      <div className="bg-bg-secondary rounded-lg shadow-xl w-full max-w-md p-8 text-center">
        {state === 'processing' && (
          <>
            <div className="w-16 h-16 mx-auto mb-4">
              <SpinnerIcon className="w-full h-full text-accent-primary animate-spin" />
            </div>
            <h1 className="text-xl font-semibold text-text-primary mb-2">
              Connecting to Google Drive
            </h1>
            <p className="text-text-secondary">
              Please wait while we complete the authentication...
            </p>
          </>
        )}

        {state === 'success' && (
          <>
            <div className="w-16 h-16 mx-auto mb-4 bg-accent-success/20 rounded-full flex items-center justify-center">
              <CheckIcon className="w-8 h-8 text-accent-success" />
            </div>
            <h1 className="text-xl font-semibold text-text-primary mb-2">
              Successfully Connected!
            </h1>
            <p className="text-text-secondary mb-4">
              Your Google account <span className="font-medium text-text-primary">{email}</span> has
              been connected.
            </p>
            <p className="text-sm text-text-muted">Redirecting to Import Sources...</p>
          </>
        )}

        {state === 'error' && (
          <>
            <div className="w-16 h-16 mx-auto mb-4 bg-accent-danger/20 rounded-full flex items-center justify-center">
              <ErrorIcon className="w-8 h-8 text-accent-danger" />
            </div>
            <h1 className="text-xl font-semibold text-text-primary mb-2">
              Authentication Failed
            </h1>
            <p className="text-text-secondary mb-4">{errorMessage}</p>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => navigate('/import-sources', { replace: true })}
                className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors"
              >
                Return to Import Sources
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 text-text-secondary hover:text-text-primary transition-colors"
              >
                Try Again
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// Icons
// =============================================================================

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="10" strokeWidth={2} strokeDasharray="60" strokeDashoffset="20" />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  )
}

function ErrorIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}
