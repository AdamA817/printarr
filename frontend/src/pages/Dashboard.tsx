export function Dashboard() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-bg-secondary rounded-lg p-6">
          <h3 className="text-text-secondary text-sm font-medium">Channels</h3>
          <p className="text-3xl font-bold text-text-primary mt-2">0</p>
        </div>
        <div className="bg-bg-secondary rounded-lg p-6">
          <h3 className="text-text-secondary text-sm font-medium">Designs</h3>
          <p className="text-3xl font-bold text-text-primary mt-2">0</p>
        </div>
        <div className="bg-bg-secondary rounded-lg p-6">
          <h3 className="text-text-secondary text-sm font-medium">Downloads</h3>
          <p className="text-3xl font-bold text-text-primary mt-2">0</p>
        </div>
      </div>

      <div className="bg-bg-secondary rounded-lg p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Welcome to Printarr
        </h3>
        <p className="text-text-secondary">
          Monitor Telegram channels for 3D-printable designs, catalog them, and
          manage downloads into your structured local library.
        </p>
        <p className="text-text-muted mt-4 text-sm">
          Get started by adding a channel in the Channels section.
        </p>
      </div>
    </div>
  )
}
