import { useState } from 'react'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import { Skeleton } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { backupService } from '../services/backup'
import { useBackups, useBackupAction } from '../hooks/useBackup'

function formatBytes(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(dateStr) {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString()
}

function BackupStatusBadge({ status }) {
  const colors = {
    completed: 'bg-green-100 text-green-700',
    in_progress: 'bg-blue-100 text-blue-700',
    failed: 'bg-red-100 text-red-700',
    pending: 'bg-yellow-100 text-yellow-700',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-gray-100 text-gray-700'}`}>
      {status?.replace('_', ' ')}
    </span>
  )
}

function RestoreWizard({ backup, onClose, onRestored }) {
  const { restore, loading } = useBackupAction()
  const [step, setStep] = useState('confirm')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleRestore = async () => {
    setError(null)
    try {
      const res = await restore(backup.id)
      setResult(res)
      setStep('done')
      onRestored?.()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div className="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4" role="dialog" aria-modal="true">
        <h2 className="text-lg font-semibold text-gray-900">
          {step === 'confirm' ? 'Restore from Backup' : 'Restore Complete'}
        </h2>

        {step === 'confirm' && (
          <>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
              <strong>Warning:</strong> Restoring from a backup will overwrite all existing data with the backed-up data. This action cannot be undone.
            </div>
            <div className="space-y-2 text-sm text-gray-600">
              <p><strong>Backup:</strong> #{backup.id}</p>
              <p><strong>Created:</strong> {formatDate(backup.created_at)}</p>
              <p><strong>Records:</strong> {backup.metadata?.total_records ?? '?'}</p>
              <p><strong>File Size:</strong> {formatBytes(backup.file_size)}</p>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="secondary" onClick={onClose} disabled={loading}>Cancel</Button>
              <Button className="bg-red-600 hover:bg-red-700 text-white" onClick={handleRestore} disabled={loading}>
                {loading ? 'Restoring...' : 'Restore Backup'}
              </Button>
            </div>
          </>
        )}

        {step === 'done' && (
          <>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
              Backup restored successfully!
            </div>
            {result?.restored_counts && (
              <div className="space-y-1 text-sm text-gray-600">
                <p className="font-medium">Restored Records:</p>
                {Object.entries(result.restored_counts).map(([model, count]) => (
                  <p key={model} className="ml-2">{model}: {count}</p>
                ))}
              </div>
            )}
            <div className="flex justify-end pt-2">
              <Button onClick={onClose}>Done</Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function ExportDialog({ onClose }) {
  const [entity, setEntity] = useState('occupants')
  const [fileFormat, setFileFormat] = useState('csv')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const entities = ['occupants', 'occupancies', 'payments', 'receipts']

  const handleExport = async () => {
    setLoading(true)
    setError(null)
    try {
      await backupService.exportData(entity, fileFormat)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4" role="dialog" aria-modal="true">
        <h2 className="text-lg font-semibold text-gray-900">Export Data</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Entity</label>
            <select
              value={entity}
              onChange={(e) => setEntity(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              {entities.map((e) => (
                <option key={e} value={e}>{e.charAt(0).toUpperCase() + e.slice(1)}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="format"
                  value="csv"
                  checked={fileFormat === 'csv'}
                  onChange={() => setFileFormat('csv')}
                  className="text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700">CSV</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="format"
                  value="xlsx"
                  checked={fileFormat === 'xlsx'}
                  onChange={() => setFileFormat('xlsx')}
                  className="text-primary-600 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700">Excel (XLSX)</span>
              </label>
            </div>
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="secondary" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button onClick={handleExport} disabled={loading}>
            {loading ? 'Exporting...' : 'Export'}
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function Backup() {
  const { data, loading, error, refetch } = useBackups()
  const { create, loading: creating } = useBackupAction()
  const [restoreTarget, setRestoreTarget] = useState(null)
  const [showExport, setShowExport] = useState(false)

  const handleCreate = async () => {
    try {
      await create()
      refetch()
    } catch {
      // error handled by hook
    }
  }

  const handleRestored = () => {
    setRestoreTarget(null)
    refetch()
  }

  return (
    <PageContainer
      title="Backup & Export"
      description="Create and manage system backups, restore data, and export records."
    >
      {restoreTarget && (
        <RestoreWizard
          backup={restoreTarget}
          onClose={() => setRestoreTarget(null)}
          onRestored={handleRestored}
        />
      )}
      {showExport && <ExportDialog onClose={() => setShowExport(false)} />}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card title="Create Backup">
          <p className="text-sm text-gray-600 mb-4">
            Create a full system backup of all properties, occupants, payments, and settings.
          </p>
          <Button onClick={handleCreate} disabled={creating}>
            {creating ? 'Creating...' : 'Create Backup Now'}
          </Button>
        </Card>

        <Card title="Export Data">
          <p className="text-sm text-gray-600 mb-4">
            Export occupants, occupancies, payments, or receipts as CSV or Excel files.
          </p>
          <Button variant="secondary" onClick={() => setShowExport(true)}>
            Open Export Dialog
          </Button>
        </Card>

        <Card title="Restore">
          <p className="text-sm text-gray-600 mb-4">
            Select a backup from the list below to restore your system to a previous state.
          </p>
          <p className="text-xs text-yellow-600 font-medium">
            This action will overwrite existing data.
          </p>
        </Card>
      </div>

      <Card title="Backup History">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
          </div>
        ) : error ? (
          <p className="text-sm text-red-600">{error}</p>
        ) : data && data.results?.length === 0 ? (
          <EmptyState icon="default" title="No backups yet" description="Create a backup using the card above to protect your data." />
        ) : data && data.results?.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-200">
                  <th className="pb-3 font-medium">ID</th>
                  <th className="pb-3 font-medium">Status</th>
                  <th className="pb-3 font-medium">Created</th>
                  <th className="pb-3 font-medium">Size</th>
                  <th className="pb-3 font-medium">Records</th>
                  <th className="pb-3 font-medium">Notes</th>
                  <th className="pb-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.results.map((backup) => (
                  <tr key={backup.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 font-medium text-gray-900">#{backup.id}</td>
                    <td className="py-3"><BackupStatusBadge status={backup.status} /></td>
                    <td className="py-3 text-gray-600">{formatDate(backup.created_at)}</td>
                    <td className="py-3 text-gray-600">{formatBytes(backup.file_size)}</td>
                    <td className="py-3 text-gray-600">{backup.metadata?.total_records ?? '—'}</td>
                    <td className="py-3 text-gray-600 max-w-[160px] truncate">{backup.notes || '—'}</td>
                    <td className="py-3">
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setRestoreTarget(backup)}
                          disabled={backup.status !== 'completed'}
                        >
                          Restore
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {data.total_pages > 1 && (
              <div className="flex justify-between items-center mt-4 pt-4 border-t border-gray-200">
                <p className="text-sm text-gray-500">
                  Page {data.page} of {data.total_pages} ({data.count} total)
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={data.page <= 1}
                    onClick={() => refetch()}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={data.page >= data.total_pages}
                    onClick={() => refetch()}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </Card>
    </PageContainer>
  )
}
