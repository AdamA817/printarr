import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  const handleTelegramAuthClick = () => {
    setAuthModalOpen(true)
  }

  return (
    <div className="flex h-screen bg-bg-primary">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          onTelegramAuthClick={handleTelegramAuthClick}
        />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      {/* TODO: TelegramAuthModal will be added in issue #26 */}
      {authModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-bg-secondary rounded-lg p-6 max-w-md w-full mx-4">
            <h2 className="text-lg font-semibold text-text-primary mb-4">
              Connect to Telegram
            </h2>
            <p className="text-text-secondary mb-4">
              Telegram authentication wizard coming in issue #26.
            </p>
            <button
              onClick={() => setAuthModalOpen(false)}
              className="w-full bg-accent-primary text-white py-2 px-4 rounded hover:bg-accent-primary/80 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
