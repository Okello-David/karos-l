import { useState, useEffect } from 'react'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import { Skeleton } from '../components/Skeleton'
import Spinner from '../components/Spinner'
import ConfirmDialog from '../components/ConfirmDialog'
import EmptyState from '../components/EmptyState'
import { useToast } from '../components/Toast'
import {
  useAdminProperties, useAdminSections, useAdminUnits,
  usePricingRules, useAdminUsers, useAdminGroups,
} from '../hooks/useAdmin'
import { adminService } from '../services/admin'
import { useAuditLogs, useAuditMeta } from '../hooks/useAudit'
import { formatUGX } from '../utils/format'

const tabs = [
  { id: 'properties', label: 'Properties' },
  { id: 'sections', label: 'Sections' },
  { id: 'units', label: 'Units' },
  { id: 'pricing', label: 'Pricing' },
  { id: 'users', label: 'Users' },
  { id: 'audit', label: 'Audit Log' },
]

function AdminFormDialog({ open, title, fields, data, onSave, onClose }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (open) setForm(data || {})
  }, [open, data])

  if (!open) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSave(form)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/40" onClick={onClose} aria-hidden="true" />
      <div className="relative bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4 max-h-[85vh] overflow-y-auto" role="dialog" aria-modal="true">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          {fields.map((f) => (
            <div key={f.name}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{f.label}</label>
              {f.type === 'select' ? (
                <select
                  value={form[f.name] ?? ''}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required={f.required}
                >
                  <option value="">{f.placeholder || 'Select...'}</option>
                  {f.options?.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : f.type === 'textarea' ? (
                <textarea
                  value={form[f.name] ?? ''}
                  onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  rows={3}
                />
              ) : (
                <input
                  type={f.type || 'text'}
                  value={form[f.name] ?? ''}
                  onChange={(e) => setForm({ ...form, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  required={f.required}
                  placeholder={f.placeholder}
                  step={f.step}
                />
              )}
            </div>
          ))}
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Saving...' : 'Save'}</Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function PropertyTab() {
  const { data: properties, loading, error, refetch } = useAdminProperties()
  const [dialog, setDialog] = useState(null)
  const [archiveConfirm, setArchiveConfirm] = useState(null)
  const { addToast } = useToast()

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'code', label: 'Code', required: true },
    { name: 'address', label: 'Address', type: 'textarea' },
    { name: 'description', label: 'Description', type: 'textarea' },
  ]

  const handleSave = async (form) => {
    if (dialog.mode === 'create') {
      await adminService.propertyCreate(form)
      addToast('Property created successfully.', { type: 'success' })
    } else {
      await adminService.propertyUpdate(dialog.item.id, form)
      addToast('Property updated successfully.', { type: 'success' })
    }
    refetch()
  }

  const handleArchive = async (id) => {
    try {
      await adminService.propertyArchive(id)
      addToast('Property archived successfully.', { type: 'success' })
      refetch()
    } catch (err) {
      addToast(err.message, { type: 'error' })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Properties</h3>
        <Button size="sm" onClick={() => setDialog({ mode: 'create', item: null, title: 'Create Property' })}>Add Property</Button>
      </div>

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : !properties?.length ? (
        <EmptyState icon="building" title="No properties found" description="Properties will appear here once they are created." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Name</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Code</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500" />
              </tr>
            </thead>
            <tbody>
              {properties.map((p) => (
                <tr key={p.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="py-3 px-4 text-gray-900 font-medium">{p.name}</td>
                  <td className="py-3 px-4 text-gray-500">{p.code}</td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${p.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                      {p.is_active ? 'Active' : 'Archived'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => setDialog({ mode: 'edit', item: p, title: 'Edit Property' })} className="text-primary-600 hover:text-primary-700 text-sm font-medium mr-3">Edit</button>
                    {p.is_active && (
                      <button onClick={() => setArchiveConfirm(p)} className="text-red-600 hover:text-red-700 text-sm font-medium">Archive</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AdminFormDialog
        open={!!dialog}
        title={dialog?.title || ''}
        fields={fields}
        data={dialog?.item || {}}
        onSave={handleSave}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        open={!!archiveConfirm}
        title="Archive Property"
        message={`Are you sure you want to archive "${archiveConfirm?.name}"? This will hide it from operational views.`}
        confirmLabel="Archive"
        onConfirm={() => { handleArchive(archiveConfirm.id); setArchiveConfirm(null) }}
        onCancel={() => setArchiveConfirm(null)}
      />
    </div>
  )
}

function SectionTab() {
  const { data: properties } = useAdminProperties()
  const [selectedProp, setSelectedProp] = useState('')
  const { data: sections, loading, error, refetch } = useAdminSections(selectedProp)
  const [dialog, setDialog] = useState(null)
  const [archiveConfirm, setArchiveConfirm] = useState(null)
  const [reorderMode, setReorderMode] = useState(false)
  const { addToast } = useToast()

  useEffect(() => {
    if (properties?.length && !selectedProp) {
      setSelectedProp(String(properties[0].id))
    }
  }, [properties, selectedProp])

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'description', label: 'Description', type: 'textarea' },
    { name: 'order', label: 'Order', type: 'number', placeholder: '0' },
  ]

  const handleSave = async (form) => {
    const payload = { ...form, property: Number(selectedProp) || form.property }
    if (dialog.mode === 'create') {
      await adminService.sectionCreate(payload)
      addToast('Section created successfully.', { type: 'success' })
    } else {
      await adminService.sectionUpdate(dialog.item.id, payload)
      addToast('Section updated successfully.', { type: 'success' })
    }
    refetch()
  }

  const handleArchive = async (id) => {
    try {
      await adminService.sectionArchive(id)
      addToast('Section archived successfully.', { type: 'success' })
      refetch()
    } catch (err) {
      addToast(err.message, { type: 'error' })
    }
  }

  const handleMoveUp = (index) => {
    if (index === 0 || !sections) return
    const newOrder = [...sections]
    ;[newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]]
    newOrder.forEach((s, i) => { s.order = i })
    adminService.sectionReorder(newOrder.map((s) => ({ id: s.id, order: s.order })))
    refetch()
  }

  const handleMoveDown = (index) => {
    if (!sections || index >= sections.length - 1) return
    const newOrder = [...sections]
    ;[newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]]
    newOrder.forEach((s, i) => { s.order = i })
    adminService.sectionReorder(newOrder.map((s) => ({ id: s.id, order: s.order })))
    refetch()
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Sections</h3>
        <div className="flex items-center gap-3">
          <select
            value={selectedProp}
            onChange={(e) => setSelectedProp(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {properties?.map((p) => (
              <option key={p.id} value={String(p.id)}>{p.name}</option>
            ))}
          </select>
          <Button size="sm" variant="ghost" onClick={() => setReorderMode(!reorderMode)}>
            {reorderMode ? 'Done' : 'Reorder'}
          </Button>
          <Button size="sm" onClick={() => setDialog({ mode: 'create', item: null, title: 'Create Section' })}>Add Section</Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : !sections?.length ? (
        <EmptyState icon="building" title="No sections" description="Sections will appear here once they are created for this property." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Order</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Name</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500" />
              </tr>
            </thead>
            <tbody>
              {sections.map((s, idx) => (
                <tr key={s.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="py-3 px-4 text-gray-500">
                    {reorderMode ? (
                      <div className="flex items-center gap-1">
                        <button onClick={() => handleMoveUp(idx)} disabled={idx === 0} className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" /></svg>
                        </button>
                        <span className="text-xs w-4 text-center">{s.order}</span>
                        <button onClick={() => handleMoveDown(idx)} disabled={idx >= sections.length - 1} className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-30">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" /></svg>
                        </button>
                      </div>
                    ) : (
                      s.order
                    )}
                  </td>
                  <td className="py-3 px-4 text-gray-900 font-medium">{s.name}</td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${s.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'}`}>
                      {s.is_active ? 'Active' : 'Archived'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => setDialog({ mode: 'edit', item: s, title: 'Edit Section' })} className="text-primary-600 hover:text-primary-700 text-sm font-medium mr-3">Edit</button>
                    {s.is_active && (
                      <button onClick={() => setArchiveConfirm(s)} className="text-red-600 hover:text-red-700 text-sm font-medium">Archive</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AdminFormDialog
        open={!!dialog}
        title={dialog?.title || ''}
        fields={fields}
        data={dialog?.item || {}}
        onSave={handleSave}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        open={!!archiveConfirm}
        title="Archive Section"
        message={`Are you sure you want to archive "${archiveConfirm?.name}"?`}
        confirmLabel="Archive"
        onConfirm={() => { handleArchive(archiveConfirm.id); setArchiveConfirm(null) }}
        onCancel={() => setArchiveConfirm(null)}
      />
    </div>
  )
}

function UnitTab() {
  const { data: properties } = useAdminProperties()
  const [selectedProp, setSelectedProp] = useState('')
  const [selectedSection, setSelectedSection] = useState('')
  const { data: sections } = useAdminSections(selectedProp)
  const { data: units, loading, error, refetch } = useAdminUnits({ section_id: selectedSection })
  const [dialog, setDialog] = useState(null)
  const [archiveConfirm, setArchiveConfirm] = useState(null)
  const { addToast } = useToast()

  useEffect(() => {
    if (properties?.length && !selectedProp) setSelectedProp(String(properties[0].id))
  }, [properties, selectedProp])

  useEffect(() => {
    setSelectedSection('')
  }, [selectedProp])

  const statusColors = {
    active: 'bg-green-100 text-green-800',
    maintenance: 'bg-yellow-100 text-yellow-800',
    archived: 'bg-gray-100 text-gray-600',
  }

  const statusLabels = {
    active: 'Active',
    maintenance: 'Maintenance',
    archived: 'Archived',
  }

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'capacity', label: 'Capacity', type: 'number', required: true },
    {
      name: 'status', label: 'Status', type: 'select', required: true,
      options: [
        { value: 'active', label: 'Active' },
        { value: 'maintenance', label: 'Maintenance' },
        { value: 'archived', label: 'Archived' },
      ],
    },
    { name: 'order', label: 'Order', type: 'number', placeholder: '0' },
    { name: 'semester_price', label: 'Semester Price', type: 'number', required: true, step: '0.01' },
    { name: 'monthly_price', label: 'Monthly Price', type: 'number', required: true, step: '0.01' },
  ]

  const handleSave = async (form) => {
    const payload = {
      ...form,
      section: Number(selectedSection) || form.section,
      semester_price: String(form.semester_price),
      monthly_price: String(form.monthly_price),
    }
    if (dialog.mode === 'create') {
      await adminService.unitCreate(payload)
      addToast('Unit created successfully.', { type: 'success' })
    } else {
      await adminService.unitUpdate(dialog.item.id, payload)
      addToast('Unit updated successfully.', { type: 'success' })
    }
    refetch()
  }

  const handleArchive = async (id) => {
    try {
      await adminService.unitArchive(id)
      addToast('Unit archived successfully.', { type: 'success' })
      refetch()
    } catch (err) {
      addToast(err.message, { type: 'error' })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Units</h3>
        <div className="flex items-center gap-3">
          <select value={selectedProp} onChange={(e) => setSelectedProp(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
            {properties?.map((p) => <option key={p.id} value={String(p.id)}>{p.name}</option>)}
          </select>
          <select value={selectedSection} onChange={(e) => setSelectedSection(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Sections</option>
            {sections?.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
          </select>
          <Button
            size="sm"
            disabled={!selectedSection}
            onClick={() => setDialog({ mode: 'create', item: null, title: 'Create Unit' })}
          >
            Add Unit
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : !units?.length ? (
        <EmptyState icon="building" title="No units found" description="Units will appear here once they are created." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Name</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden sm:table-cell">Section</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden md:table-cell">Capacity</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden lg:table-cell">Semester</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden xl:table-cell">Monthly</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500" />
              </tr>
            </thead>
            <tbody>
              {units.map((u) => (
                <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="py-3 px-4 text-gray-900 font-medium">{u.name}</td>
                  <td className="py-3 px-4 text-gray-500 hidden sm:table-cell">{u.section_name}</td>
                  <td className="py-3 px-4 text-gray-500 hidden md:table-cell">{u.capacity}</td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[u.status] || ''}`}>
                      {statusLabels[u.status] || u.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-gray-500 hidden lg:table-cell">{formatUGX(u.semester_price)}</td>
                  <td className="py-3 px-4 text-gray-500 hidden xl:table-cell">{formatUGX(u.monthly_price)}</td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => setDialog({ mode: 'edit', item: u, title: 'Edit Unit' })} className="text-primary-600 hover:text-primary-700 text-sm font-medium mr-3">Edit</button>
                    {u.status === 'active' && (
                      <button onClick={() => setArchiveConfirm(u)} className="text-red-600 hover:text-red-700 text-sm font-medium">Archive</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AdminFormDialog
        open={!!dialog}
        title={dialog?.title || ''}
        fields={fields}
        data={dialog?.item || {}}
        onSave={handleSave}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        open={!!archiveConfirm}
        title="Archive Unit"
        message={`Are you sure you want to archive "${archiveConfirm?.name}"?`}
        confirmLabel="Archive"
        onConfirm={() => { handleArchive(archiveConfirm.id); setArchiveConfirm(null) }}
        onCancel={() => setArchiveConfirm(null)}
      />
    </div>
  )
}

function PricingTab() {
  const { data: properties } = useAdminProperties()
  const [selectedProp, setSelectedProp] = useState('')
  const [selectedSection, setSelectedSection] = useState('')
  const [selectedUnit, setSelectedUnit] = useState('')
  const { data: sections } = useAdminSections(selectedProp)
  const { data: units } = useAdminUnits({ section_id: selectedSection })
  const { data: rules, loading, error, refetch } = usePricingRules({ unit_id: selectedUnit })
  const [dialog, setDialog] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const { addToast } = useToast()

  useEffect(() => {
    if (properties?.length && !selectedProp) setSelectedProp(String(properties[0].id))
  }, [properties, selectedProp])

  useEffect(() => { setSelectedSection('') }, [selectedProp])
  useEffect(() => { setSelectedUnit('') }, [selectedSection])

  const fields = [
    { name: 'billing_mode', label: 'Billing Mode', type: 'select', required: true,
      options: [
        { value: 'semester', label: 'Semester' },
        { value: 'monthly', label: 'Monthly' },
      ],
    },
    { name: 'price', label: 'Price', type: 'number', required: true, step: '0.01' },
    { name: 'effective_date', label: 'Effective Date', type: 'date', required: true },
  ]

  const handleSave = async (form) => {
    const payload = {
      ...form,
      unit: Number(selectedUnit),
      price: String(form.price),
    }
    if (dialog.mode === 'create') {
      await adminService.pricingRuleCreate(payload)
      addToast('Pricing rule created successfully.', { type: 'success' })
    } else {
      await adminService.pricingRuleUpdate(dialog.item.id, payload)
      addToast('Pricing rule updated successfully.', { type: 'success' })
    }
    refetch()
  }

  const handleDelete = async (id) => {
    try {
      await adminService.pricingRuleDelete(id)
      addToast('Pricing rule deleted.', { type: 'success' })
      refetch()
    } catch (err) {
      addToast(err.message, { type: 'error' })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Pricing Rules</h3>
        <div className="flex items-center gap-3">
          <select value={selectedProp} onChange={(e) => setSelectedProp(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
            {properties?.map((p) => <option key={p.id} value={String(p.id)}>{p.name}</option>)}
          </select>
          <select value={selectedSection} onChange={(e) => setSelectedSection(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Sections</option>
            {sections?.map((s) => <option key={s.id} value={String(s.id)}>{s.name}</option>)}
          </select>
          <select value={selectedUnit} onChange={(e) => setSelectedUnit(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500">
            <option value="">All Units</option>
            {units?.map((u) => <option key={u.id} value={String(u.id)}>{u.name}</option>)}
          </select>
          {selectedUnit && (
            <Button size="sm" onClick={() => setDialog({ mode: 'create', item: null, title: 'Add Pricing Rule' })}>Add Rule</Button>
          )}
        </div>
      </div>

      {!selectedUnit ? (
        <EmptyState icon="currency" title="Select a unit" description="Choose a unit from the dropdown above to view its pricing rules." />
      ) : loading ? (
        <div className="space-y-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : !rules?.length ? (
        <EmptyState icon="currency" title="No pricing rules" description="No pricing rules for this unit. Prices default to unit-level semester/monthly prices." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Billing Mode</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Price</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Effective Date</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500" />
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="py-3 px-4 text-gray-900 font-medium capitalize">{r.billing_mode}</td>
                  <td className="py-3 px-4 text-gray-900">{formatUGX(r.price)}</td>
                  <td className="py-3 px-4 text-gray-500">{new Date(r.effective_date).toLocaleDateString()}</td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => setDeleteConfirm(r)} className="text-red-600 hover:text-red-700 text-sm font-medium">Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AdminFormDialog
        open={!!dialog}
        title={dialog?.title || ''}
        fields={fields}
        data={dialog?.item || {}}
        onSave={handleSave}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        open={!!deleteConfirm}
        title="Delete Pricing Rule"
        message={`Delete pricing rule for ${deleteConfirm?.billing_mode} at ${formatUGX(deleteConfirm?.price || 0)}?`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => { handleDelete(deleteConfirm.id); setDeleteConfirm(null) }}
        onCancel={() => setDeleteConfirm(null)}
      />

      <Card title="How Pricing Works" className="mt-6">
        <ol className="list-decimal list-inside text-sm text-gray-600 space-y-2">
          <li>When an occupant is assigned, the current price is snapshotted into their occupancy record.</li>
          <li>Adding a new pricing rule does NOT change prices for existing occupancies.</li>
          <li>New assignments will use the most recent pricing rule (by effective date) for that billing mode.</li>
          <li>If no pricing rule exists, the unit&apos;s default semester_price / monthly_price fields are used.</li>
          <li>To change prices for existing occupancies, edit the unit&apos;s default prices directly.</li>
        </ol>
      </Card>
    </div>
  )
}

function UsersTab() {
  const { data: users, loading, error, refetch } = useAdminUsers()
  const { data: groups } = useAdminGroups()
  const [dialog, setDialog] = useState(null)
  const [toggleConfirm, setToggleConfirm] = useState(null)
  const { addToast } = useToast()

  const fields = [
    { name: 'username', label: 'Username', required: true },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'first_name', label: 'First Name' },
    { name: 'last_name', label: 'Last Name' },
    { name: 'password', label: 'Password', type: 'password', placeholder: dialog?.mode === 'edit' ? 'Leave blank to keep current' : '' },
    { name: 'is_staff', label: 'Staff Access', type: 'select', options: [{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }] },
    { name: 'is_superuser', label: 'Super Admin', type: 'select', options: [{ value: 'true', label: 'Yes' }, { value: 'false', label: 'No' }] },
  ]

  const handleSave = async (form) => {
    const payload = {
      ...form,
      is_staff: form.is_staff === 'true',
      is_superuser: form.is_superuser === 'true',
    }
    if (dialog.mode === 'create') {
      await adminService.userCreate(payload)
      addToast('User created successfully.', { type: 'success' })
    } else {
      await adminService.userUpdate(dialog.item.id, payload)
      addToast('User updated successfully.', { type: 'success' })
    }
    refetch()
  }

  const handleToggle = async (id) => {
    try {
      await adminService.userToggleActive(id)
      addToast('User status toggled.', { type: 'success' })
      refetch()
    } catch (err) {
      addToast(err.message, { type: 'error' })
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Users</h3>
        <Button size="sm" onClick={() => setDialog({ mode: 'create', item: null, title: 'Create User' })}>Add User</Button>
      </div>

      <Card title="Roles & Permissions" subtitle="Available system groups">
        {groups ? (
          <div className="flex flex-wrap gap-2">
            {groups.map((g) => (
              <span key={g.id} className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-primary-50 text-primary-700">{g.name}</span>
            ))}
          </div>
        ) : (
          <div className="flex gap-2">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-6 w-20 rounded-full" />)}
          </div>
        )}
      </Card>

      {loading ? (
        <div className="space-y-3">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : !users?.length ? (
        <EmptyState icon="people" title="No users found" description="Users will appear here once they are created." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-medium text-gray-500">Username</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden sm:table-cell">Name</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden md:table-cell">Email</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500 hidden lg:table-cell">Role</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500">Status</th>
                <th className="text-left py-3 px-4 font-medium text-gray-500" />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-gray-100 last:border-0 hover:bg-gray-50">
                  <td className="py-3 px-4 text-gray-900 font-medium">{u.username}</td>
                  <td className="py-3 px-4 text-gray-500 hidden sm:table-cell">{[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}</td>
                  <td className="py-3 px-4 text-gray-500 hidden md:table-cell">{u.email || '—'}</td>
                  <td className="py-3 px-4 hidden lg:table-cell">
                    {u.is_superuser ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">Super Admin</span>
                    ) : u.is_staff ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">Staff</span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">User</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${u.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button onClick={() => setDialog({ mode: 'edit', item: u, title: 'Edit User' })} className="text-primary-600 hover:text-primary-700 text-sm font-medium mr-3">Edit</button>
                    <button onClick={() => setToggleConfirm(u)} className="text-red-600 hover:text-red-700 text-sm font-medium">
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <AdminFormDialog
        open={!!dialog}
        title={dialog?.title || ''}
        fields={fields}
        data={dialog?.item ? { ...dialog.item, is_staff: String(dialog.item.is_staff), is_superuser: String(dialog.item.is_superuser) } : {}}
        onSave={handleSave}
        onClose={() => setDialog(null)}
      />

      <ConfirmDialog
        open={!!toggleConfirm}
        title={toggleConfirm?.is_active ? 'Deactivate User' : 'Activate User'}
        message={`${toggleConfirm?.is_active ? 'Deactivate' : 'Activate'} user "${toggleConfirm?.username}"?`}
        confirmLabel={toggleConfirm?.is_active ? 'Deactivate' : 'Activate'}
        variant="danger"
        onConfirm={() => { handleToggle(toggleConfirm.id); setToggleConfirm(null) }}
        onCancel={() => setToggleConfirm(null)}
      />
    </div>
  )
}

function AuditLogTab() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ entity_type: '', action: '', date_from: '', date_to: '' })
  const { data, loading, error, refetch } = useAuditLogs({ ...filters, page })
  const { entityTypes, actions, loading: metaLoading } = useAuditMeta()
  const [detail, setDetail] = useState(null)

  const pageSize = 20

  const actionColors = {
    create: 'bg-green-100 text-green-800',
    update: 'bg-blue-100 text-blue-800',
    delete: 'bg-red-100 text-red-800',
    archive: 'bg-yellow-100 text-yellow-800',
    assign: 'bg-purple-100 text-purple-800',
    checkout: 'bg-orange-100 text-orange-800',
    record_payment: 'bg-teal-100 text-teal-800',
    other: 'bg-gray-100 text-gray-600',
  }

  const highlightEntity = (entity) => {
    const colors = {
      occupant: 'text-indigo-600',
      occupancy: 'text-purple-600',
      payment: 'text-teal-600',
      receipt: 'text-cyan-600',
      property: 'text-blue-600',
      section: 'text-sky-600',
      unit: 'text-violet-600',
      pricing_rule: 'text-amber-600',
      user: 'text-gray-600',
    }
    return colors[entity] || 'text-gray-600'
  }

  const handleFilterChange = (key, value) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
    setPage(1)
  }

  const totalPages = data ? data.total_pages : 0

  if (detail) {
    return (
      <div className="space-y-4">
        <button onClick={() => setDetail(null)} className="text-primary-600 hover:text-primary-700 text-sm font-medium flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
          Back to Audit Log
        </button>
        <Card title="Audit Log Detail">
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-gray-500 font-medium">ID</dt>
              <dd className="text-gray-900 mt-0.5">#{detail.id}</dd>
            </div>
            <div>
              <dt className="text-gray-500 font-medium">Timestamp</dt>
              <dd className="text-gray-900 mt-0.5">{new Date(detail.timestamp).toLocaleString()}</dd>
            </div>
            <div>
              <dt className="text-gray-500 font-medium">Actor</dt>
              <dd className="text-gray-900 mt-0.5">{detail.actor?.username || 'System'}</dd>
            </div>
            <div>
              <dt className="text-gray-500 font-medium">IP Address</dt>
              <dd className="text-gray-900 mt-0.5">{detail.ip_address || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500 font-medium">Entity Type</dt>
              <dd className="text-gray-900 mt-0.5">
                <span className={`font-medium capitalize ${highlightEntity(detail.entity_type)}`}>
                  {detail.entity_type_display}
                </span>
                {detail.entity_id && <span className="text-gray-500"> #{detail.entity_id}</span>}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500 font-medium">Action</dt>
              <dd className="mt-0.5">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${actionColors[detail.action] || 'bg-gray-100 text-gray-600'}`}>
                  {detail.action_display}
                </span>
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-gray-500 font-medium">Description</dt>
              <dd className="text-gray-900 mt-0.5">{detail.description}</dd>
            </div>
            {detail.changes && (
              <div className="sm:col-span-2">
                <dt className="text-gray-500 font-medium">Changes</dt>
                <dd className="mt-0.5">
                  <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-700 overflow-x-auto max-h-64">
                    {JSON.stringify(detail.changes, null, 2)}
                  </pre>
                </dd>
              </div>
            )}
          </dl>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">Activity Timeline</h3>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Entity Type</label>
          <select
            value={filters.entity_type}
            onChange={(e) => handleFilterChange('entity_type', e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Types</option>
            {entityTypes.map((et) => (
              <option key={et.value} value={et.value}>{et.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">Action</label>
          <select
            value={filters.action}
            onChange={(e) => handleFilterChange('action', e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">All Actions</option>
            {actions.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">From</label>
          <input
            type="date"
            value={filters.date_from}
            onChange={(e) => handleFilterChange('date_from', e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-gray-500">To</label>
          <input
            type="date"
            value={filters.date_to}
            onChange={(e) => handleFilterChange('date_to', e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>
        <Button variant="ghost" size="sm" onClick={() => { setFilters({ entity_type: '', action: '', date_from: '', date_to: '' }); setPage(1) }}>
          Clear
        </Button>
      </div>

      {/* Timeline */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      ) : error ? (
        <p className="text-red-600">{error}</p>
      ) : !data?.results?.length ? (
        <EmptyState icon="default" title="No audit log entries" description="Audit events will appear here as actions are performed." />
      ) : (
        <>
          <div className="space-y-3">
            {data.results.map((log) => (
              <button
                key={log.id}
                onClick={() => setDetail(log)}
                className="w-full text-left bg-white border border-gray-200 rounded-lg p-4 hover:border-primary-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 mt-1.5 ${actionColors[log.action]?.split(' ')[0] || 'bg-gray-300'}`} />
                    <div className="min-w-0">
                      <p className="text-sm text-gray-900 truncate">{log.description}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        <span className={`font-medium capitalize ${highlightEntity(log.entity_type)}`}>{log.entity_type_display}</span>
                        {' '}&middot;{' '}
                        <span className="font-medium">{log.action_display}</span>
                        {' '}&middot;{' '}
                        {log.actor?.username || 'System'}
                      </p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 flex-shrink-0 whitespace-nowrap">
                    {new Date(log.timestamp).toLocaleString()}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-center items-center gap-2 pt-4">
              <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              <span className="text-sm text-gray-500">
                Page {page} of {totalPages}
              </span>
              <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

const tabComponents = {
  properties: PropertyTab,
  sections: SectionTab,
  units: UnitTab,
  pricing: PricingTab,
  users: UsersTab,
  audit: AuditLogTab,
}

export default function Administration() {
  const [activeTab, setActiveTab] = useState('properties')
  const TabComponent = tabComponents[activeTab]

  return (
    <PageContainer
      title="Administration"
      description="Manage properties, sections, units, pricing rules, and system users."
    >
      <div className="border-b border-gray-200 overflow-x-auto">
        <nav className="flex gap-6 -mb-px" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors flex-shrink-0 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="pt-6">
        <TabComponent />
      </div>
    </PageContainer>
  )
}
