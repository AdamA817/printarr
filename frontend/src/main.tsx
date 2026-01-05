import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SSEProvider } from '@/contexts/SSEContext'
import './index.css'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SSEProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </SSEProvider>
    </QueryClientProvider>
  </StrictMode>
)
