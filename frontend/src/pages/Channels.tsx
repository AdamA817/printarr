export function Channels() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-bold text-text-primary">Channels</h1>
        <button className="px-4 py-2 bg-accent-primary text-white rounded-lg hover:bg-accent-primary/80 transition-colors">
          Add Channel
        </button>
      </div>

      <div className="bg-bg-secondary rounded-lg p-6">
        <p className="text-text-secondary text-center py-8">
          No channels added yet. Click "Add Channel" to get started.
        </p>
      </div>
    </div>
  )
}
