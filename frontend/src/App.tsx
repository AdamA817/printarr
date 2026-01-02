import { Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Designs } from '@/pages/Designs'
import { DesignDetail } from '@/pages/DesignDetail'
import { Channels } from '@/pages/Channels'
import { Activity } from '@/pages/Activity'
import { Settings } from '@/pages/Settings'
import { ImportSources } from '@/pages/ImportSources'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="designs" element={<Designs />} />
        <Route path="designs/:id" element={<DesignDetail />} />
        <Route path="channels" element={<Channels />} />
        <Route path="activity" element={<Activity />} />
        <Route path="settings" element={<Settings />} />
        <Route path="import-sources" element={<ImportSources />} />
      </Route>
    </Routes>
  )
}

export default App
