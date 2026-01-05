/**
 * SSE Context Provider (#222)
 *
 * Provides SSE connection state to the entire app.
 * Wrap your app with <SSEProvider> to enable real-time updates.
 */

import { createContext, useContext, type ReactNode } from 'react'
import { useSSE } from '@/hooks/useSSE'
import type { ConnectionStatus, SSEEvent } from '@/types/events'

interface SSEContextValue {
  status: ConnectionStatus
  lastEvent: SSEEvent | null
  reconnect: () => void
  disconnect: () => void
}

const SSEContext = createContext<SSEContextValue | null>(null)

interface SSEProviderProps {
  children: ReactNode
  enabled?: boolean
}

export function SSEProvider({ children, enabled = true }: SSEProviderProps) {
  const sse = useSSE({ enabled })

  return (
    <SSEContext.Provider value={sse}>
      {children}
    </SSEContext.Provider>
  )
}

export function useSSEContext() {
  const context = useContext(SSEContext)
  if (!context) {
    throw new Error('useSSEContext must be used within SSEProvider')
  }
  return context
}

// Optional: hook that returns null if context not available (for conditional usage)
export function useSSEStatus(): ConnectionStatus | null {
  const context = useContext(SSEContext)
  return context?.status ?? null
}
