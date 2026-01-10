import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Designs } from '@/pages/Designs'
import { DesignDetail } from '@/pages/DesignDetail'
import { FamilyDetail } from '@/pages/FamilyDetail'
import { Channels } from '@/pages/Channels'
import { Activity } from '@/pages/Activity'
import { Settings } from '@/pages/Settings'
import { ImportSources } from '@/pages/ImportSources'
import { ImportProfiles } from '@/pages/ImportProfiles'
import { GoogleOAuthCallback } from '@/pages/GoogleOAuthCallback'

function App() {
  return (
    <Routes>
      {/* OAuth callback - outside layout */}
      <Route path="/oauth/google/callback" element={<GoogleOAuthCallback />} />

      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="designs" element={<Designs />} />
        <Route path="designs/:id" element={<DesignDetail />} />
        <Route path="families/:id" element={<FamilyDetail />} />
        <Route path="channels" element={<Channels />} />
        <Route path="activity" element={<Activity />} />
        <Route path="settings" element={<Settings />} />
        <Route path="import-sources" element={<ImportSources />} />
        <Route path="import-profiles" element={<ImportProfiles />} />
      </Route>
    </Routes>
  )
}

export default App
