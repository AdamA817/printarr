import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useChannels } from '../useChannels'
import type { ReactNode } from 'react'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

function createWrapper() {
  const queryClient = createTestQueryClient()
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    )
  }
}

describe('useChannels', () => {
  it('fetches channels successfully', async () => {
    const { result } = renderHook(() => useChannels(), {
      wrapper: createWrapper(),
    })

    // Initially loading
    expect(result.current.isLoading).toBe(true)

    // Wait for data
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    // Check returned data
    expect(result.current.data).toBeDefined()
    expect(result.current.data?.items).toHaveLength(1)
    expect(result.current.data?.items[0].title).toBe('Test Channel')
  })

  it('returns correct pagination info', async () => {
    const { result } = renderHook(() => useChannels(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.total).toBe(1)
    expect(result.current.data?.page).toBe(1)
    expect(result.current.data?.pages).toBe(1)
  })
})
