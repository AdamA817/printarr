import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { TelegramAuthModal } from '@/components/telegram/TelegramAuthModal'

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)

  const handleTelegramAuthClick = () => {
    setAuthModalOpen(true)
  }

  const handleAuthSuccess = () => {
    // Modal will close itself after success
    // Status indicator will auto-refresh via React Query
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

      {/* Telegram Auth Modal */}
      <TelegramAuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={handleAuthSuccess}
      />
    </div>
  )
}
