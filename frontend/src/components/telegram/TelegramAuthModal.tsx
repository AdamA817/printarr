import { useState, useEffect } from 'react'
import { useStartAuth, useVerifyAuth } from '@/hooks/useTelegramStatus'
import type { TelegramErrorResponse } from '@/types/telegram'
import { AxiosError } from 'axios'

type AuthStep = 'phone' | 'code' | '2fa' | 'success'

interface TelegramAuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function TelegramAuthModal({
  isOpen,
  onClose,
  onSuccess,
}: TelegramAuthModalProps) {
  const [step, setStep] = useState<AuthStep>('phone')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [phoneCodeHash, setPhoneCodeHash] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [retryAfter, setRetryAfter] = useState<number | null>(null)
  const [showPassword, setShowPassword] = useState(false)

  const startAuth = useStartAuth()
  const verifyAuth = useVerifyAuth()

  // Reset state when modal opens
  useEffect(() => {
    if (isOpen) {
      setStep('phone')
      setPhone('')
      setCode('')
      setPassword('')
      setPhoneCodeHash('')
      setError(null)
      setRetryAfter(null)
    }
  }, [isOpen])

  // Countdown timer for rate limits
  useEffect(() => {
    if (retryAfter && retryAfter > 0) {
      const timer = setTimeout(() => {
        setRetryAfter(retryAfter - 1)
      }, 1000)
      return () => clearTimeout(timer)
    }
  }, [retryAfter])

  const handleError = (err: unknown) => {
    if (err instanceof AxiosError && err.response?.data) {
      const errorData = err.response.data as TelegramErrorResponse
      setError(errorData.message || 'An error occurred')
      if (errorData.retry_after) {
        setRetryAfter(errorData.retry_after)
      }
    } else {
      setError('An unexpected error occurred')
    }
  }

  const handlePhoneSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      const result = await startAuth.mutateAsync({ phone })
      setPhoneCodeHash(result.phone_code_hash)
      setStep('code')
    } catch (err) {
      handleError(err)
    }
  }

  const handleCodeSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      const result = await verifyAuth.mutateAsync({
        phone,
        code,
        phone_code_hash: phoneCodeHash,
      })

      if (result.status === '2fa_required') {
        setStep('2fa')
      } else if (result.status === 'authenticated') {
        setStep('success')
        setTimeout(() => {
          onSuccess?.()
          onClose()
        }, 2000)
      }
    } catch (err) {
      handleError(err)
    }
  }

  const handle2FASubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    try {
      const result = await verifyAuth.mutateAsync({
        phone,
        code,
        phone_code_hash: phoneCodeHash,
        password,
      })

      if (result.status === 'authenticated') {
        setStep('success')
        setTimeout(() => {
          onSuccess?.()
          onClose()
        }, 2000)
      }
    } catch (err) {
      handleError(err)
    }
  }

  const handleBack = () => {
    setError(null)
    if (step === 'code') {
      setStep('phone')
      setCode('')
    } else if (step === '2fa') {
      setStep('code')
      setPassword('')
    }
  }

  const handleResendCode = async () => {
    setError(null)
    try {
      const result = await startAuth.mutateAsync({ phone })
      setPhoneCodeHash(result.phone_code_hash)
      setCode('')
    } catch (err) {
      handleError(err)
    }
  }

  if (!isOpen) return null

  const isLoading = startAuth.isPending || verifyAuth.isPending
  const isRateLimited = retryAfter !== null && retryAfter > 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={!isLoading ? onClose : undefined}
      />

      {/* Modal */}
      <div className="relative bg-bg-secondary rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-bg-tertiary">
          <div className="flex items-center gap-3">
            <TelegramLogo className="w-8 h-8" />
            <h2 className="text-lg font-semibold text-text-primary">
              Connect to Telegram
            </h2>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
            aria-label="Close"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center justify-center gap-2 py-3 bg-bg-tertiary/50">
          <StepIndicator step={1} currentStep={step} label="Phone" />
          <StepConnector active={step !== 'phone'} />
          <StepIndicator step={2} currentStep={step} label="Code" />
          <StepConnector active={step === '2fa' || step === 'success'} />
          <StepIndicator step={3} currentStep={step} label="Verify" />
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Error Display */}
          {error && (
            <div className="mb-4 p-3 bg-accent-danger/20 border border-accent-danger/30 rounded-lg">
              <p className="text-sm text-accent-danger">{error}</p>
              {isRateLimited && (
                <p className="text-xs text-accent-danger/80 mt-1">
                  Please wait {retryAfter} seconds before trying again.
                </p>
              )}
            </div>
          )}

          {/* Phone Step */}
          {step === 'phone' && (
            <form onSubmit={handlePhoneSubmit}>
              <p className="text-text-secondary text-sm mb-4">
                Enter your phone number to receive a verification code via
                Telegram or SMS.
              </p>
              <div className="mb-4">
                <label
                  htmlFor="phone"
                  className="block text-sm font-medium text-text-primary mb-2"
                >
                  Phone Number
                </label>
                <input
                  id="phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+1 234 567 8900"
                  className="w-full bg-bg-tertiary border border-bg-tertiary focus:border-accent-primary rounded-lg px-4 py-2.5 text-text-primary placeholder:text-text-muted outline-none transition-colors"
                  autoFocus
                  disabled={isLoading || isRateLimited}
                  required
                />
                <p className="text-xs text-text-muted mt-1">
                  Include your country code (e.g., +1 for US)
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2.5 text-text-secondary hover:text-text-primary border border-bg-tertiary rounded-lg transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading || isRateLimited || !phone.trim()}
                  className="flex-1 px-4 py-2.5 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isLoading ? <Spinner /> : null}
                  {isLoading ? 'Sending...' : 'Send Code'}
                </button>
              </div>
            </form>
          )}

          {/* Code Step */}
          {step === 'code' && (
            <form onSubmit={handleCodeSubmit}>
              <p className="text-text-secondary text-sm mb-4">
                We sent a verification code to{' '}
                <span className="text-text-primary font-medium">{phone}</span>.
                Enter it below.
              </p>
              <div className="mb-4">
                <label
                  htmlFor="code"
                  className="block text-sm font-medium text-text-primary mb-2"
                >
                  Verification Code
                </label>
                <input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  value={code}
                  onChange={(e) =>
                    setCode(e.target.value.replace(/\D/g, '').slice(0, 6))
                  }
                  placeholder="12345"
                  className="w-full bg-bg-tertiary border border-bg-tertiary focus:border-accent-primary rounded-lg px-4 py-2.5 text-text-primary text-center text-2xl tracking-widest placeholder:text-text-muted outline-none transition-colors"
                  autoFocus
                  disabled={isLoading || isRateLimited}
                  required
                  maxLength={6}
                />
              </div>
              <button
                type="button"
                onClick={handleResendCode}
                disabled={isLoading || isRateLimited}
                className="text-sm text-accent-primary hover:text-accent-primary/80 mb-4 disabled:opacity-50"
              >
                {isRateLimited
                  ? `Resend code in ${retryAfter}s`
                  : "Didn't receive the code? Resend"}
              </button>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2.5 text-text-secondary hover:text-text-primary border border-bg-tertiary rounded-lg transition-colors disabled:opacity-50"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isLoading || isRateLimited || code.length < 5}
                  className="flex-1 px-4 py-2.5 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isLoading ? <Spinner /> : null}
                  {isLoading ? 'Verifying...' : 'Verify'}
                </button>
              </div>
            </form>
          )}

          {/* 2FA Step */}
          {step === '2fa' && (
            <form onSubmit={handle2FASubmit}>
              <p className="text-text-secondary text-sm mb-4">
                Your account has two-factor authentication enabled. Please enter
                your password.
              </p>
              <div className="mb-4">
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-text-primary mb-2"
                >
                  2FA Password
                </label>
                <div className="relative">
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your 2FA password"
                    className="w-full bg-bg-tertiary border border-bg-tertiary focus:border-accent-primary rounded-lg px-4 py-2.5 pr-12 text-text-primary placeholder:text-text-muted outline-none transition-colors"
                    autoFocus
                    disabled={isLoading}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? (
                      <EyeOffIcon className="w-5 h-5" />
                    ) : (
                      <EyeIcon className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleBack}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2.5 text-text-secondary hover:text-text-primary border border-bg-tertiary rounded-lg transition-colors disabled:opacity-50"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={isLoading || !password.trim()}
                  className="flex-1 px-4 py-2.5 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {isLoading ? <Spinner /> : null}
                  {isLoading ? 'Verifying...' : 'Sign In'}
                </button>
              </div>
            </form>
          )}

          {/* Success Step */}
          {step === 'success' && (
            <div className="text-center py-4">
              <div className="w-16 h-16 bg-accent-success/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <CheckIcon className="w-8 h-8 text-accent-success" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary mb-2">
                Successfully Connected!
              </h3>
              <p className="text-text-secondary text-sm">
                Your Telegram account is now connected. This window will close
                automatically.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Helper Components

function StepIndicator({
  step,
  currentStep,
  label,
}: {
  step: number
  currentStep: AuthStep
  label: string
}) {
  const stepOrder: AuthStep[] = ['phone', 'code', '2fa', 'success']
  const currentIndex = stepOrder.indexOf(currentStep)
  const isActive = currentIndex >= step - 1
  const isComplete =
    currentIndex > step - 1 ||
    (step === 3 && (currentStep === '2fa' || currentStep === 'success'))

  return (
    <div className="flex flex-col items-center">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
          isComplete
            ? 'bg-accent-success text-white'
            : isActive
              ? 'bg-accent-primary text-white'
              : 'bg-bg-tertiary text-text-muted'
        }`}
      >
        {isComplete ? <CheckIcon className="w-4 h-4" /> : step}
      </div>
      <span
        className={`text-xs mt-1 ${isActive ? 'text-text-primary' : 'text-text-muted'}`}
      >
        {label}
      </span>
    </div>
  )
}

function StepConnector({ active }: { active: boolean }) {
  return (
    <div
      className={`w-12 h-0.5 ${active ? 'bg-accent-primary' : 'bg-bg-tertiary'}`}
    />
  )
}

function Spinner() {
  return (
    <svg
      className="animate-spin w-4 h-4"
      fill="none"
      viewBox="0 0 24 24"
    >
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

function TelegramLogo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="#229ED9">
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.12.02-1.96 1.25-5.54 3.66-.52.36-1 .53-1.42.52-.47-.01-1.37-.26-2.03-.48-.82-.27-1.47-.42-1.42-.88.03-.24.37-.49 1.02-.74 3.99-1.73 6.65-2.87 7.97-3.43 3.8-1.57 4.59-1.85 5.1-1.85.11 0 .37.03.53.17.14.12.18.28.2.45-.01.06.01.24 0 .38z" />
    </svg>
  )
}

function CloseIcon({ className }: { className?: string }) {
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
        d="M6 18L18 6M6 6l12 12"
      />
    </svg>
  )
}

function CheckIcon({ className }: { className?: string }) {
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
        d="M5 13l4 4L19 7"
      />
    </svg>
  )
}

function EyeIcon({ className }: { className?: string }) {
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
        d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
      />
    </svg>
  )
}

function EyeOffIcon({ className }: { className?: string }) {
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
        d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"
      />
    </svg>
  )
}
