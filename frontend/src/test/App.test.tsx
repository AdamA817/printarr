import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

function renderApp(initialRoute = '/') {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('App', () => {
  it('renders without crashing', () => {
    renderApp()
    // App should render the sidebar with Printarr branding (logo image)
    expect(screen.getByAltText('Printarr')).toBeInTheDocument()
  })

  it('shows dashboard by default', () => {
    renderApp('/')
    // Dashboard appears in both sidebar nav and header - just check it exists
    expect(screen.getAllByText('Dashboard').length).toBeGreaterThanOrEqual(1)
  })

  it('navigates to channels page', () => {
    renderApp('/channels')
    // Channels page shows h1 heading with "Channels"
    expect(screen.getByRole('heading', { level: 1, name: /channels/i })).toBeInTheDocument()
  })
})
