import { useState, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import PageContainer from '../components/PageContainer'
import Card from '../components/Card'
import Button from '../components/Button'
import { Skeleton } from '../components/Skeleton'
import { occupantsService } from '../services/occupants'
import { useToast } from '../components/Toast'

export default function OccupantForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const isEditing = Boolean(id)
  const { addToast } = useToast()

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    student_id_number: '',
    national_id: '',
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(isEditing)
  const [submitError, setSubmitError] = useState(null)

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setFetching(true)
    occupantsService
      .get(id)
      .then((data) => {
        if (!cancelled) {
          setForm({
            first_name: data.first_name || '',
            last_name: data.last_name || '',
            email: data.email || '',
            phone: data.phone || '',
            student_id_number: data.student_id_number || '',
            national_id: data.national_id || '',
          })
        }
      })
      .catch((err) => setSubmitError(err.message))
      .finally(() => {
        if (!cancelled) setFetching(false)
      })
    return () => { cancelled = true }
  }, [id])

  const validate = () => {
    const errs = {}
    if (!form.first_name.trim()) errs.first_name = 'First name is required.'
    if (!form.last_name.trim()) errs.last_name = 'Last name is required.'
    if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      errs.email = 'Enter a valid email address.'
    }
    if (form.phone && !/^\+?[\d\s\-()]{7,20}$/.test(form.phone)) {
      errs.phone = 'Enter a valid phone number.'
    }
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    setSubmitError(null)
    try {
      if (isEditing) {
        await occupantsService.update(id, form)
        addToast('Occupant updated successfully.', { type: 'success' })
      } else {
        await occupantsService.create(form)
        addToast('Occupant created successfully.', { type: 'success' })
      }
      navigate('/occupants')
    } catch (err) {
      setSubmitError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (fetching) {
    return (
      <PageContainer title={isEditing ? 'Edit Occupant' : 'Add Occupant'} description="Loading...">
        <Card>
          <div className="space-y-4">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        </Card>
      </PageContainer>
    )
  }

  const fields = [
    { name: 'first_name', label: 'First Name', required: true, type: 'text' },
    { name: 'last_name', label: 'Last Name', required: true, type: 'text' },
    { name: 'email', label: 'Email', required: false, type: 'email' },
    { name: 'phone', label: 'Phone', required: false, type: 'tel', placeholder: '+256700000000' },
    { name: 'student_id_number', label: 'Student ID', required: false, type: 'text' },
    { name: 'national_id', label: 'National ID', required: false, type: 'text' },
  ]

  return (
    <PageContainer
      title={isEditing ? 'Edit Occupant' : 'Add Occupant'}
      description={isEditing ? 'Update occupant details.' : 'Register a new occupant.'}
    >
      <div className="max-w-2xl">
        <Card>
          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-6">
              {fields.map((field) => (
                <div key={field.name}>
                  <label htmlFor={field.name} className="block text-sm font-medium text-gray-700 mb-1">
                    {field.label}
                    {field.required && <span className="text-red-500 ml-0.5">*</span>}
                  </label>
                  <input
                    id={field.name}
                    name={field.name}
                    type={field.type}
                    placeholder={field.placeholder || ''}
                    value={form[field.name]}
                    onChange={handleChange}
                    className={`w-full px-4 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                      errors[field.name]
                        ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
                        : 'border-gray-300 focus:border-primary-500'
                    }`}
                    aria-invalid={!!errors[field.name]}
                    aria-describedby={errors[field.name] ? `${field.name}-error` : undefined}
                  />
                  {errors[field.name] && (
                    <p id={`${field.name}-error`} className="mt-1 text-sm text-red-600">
                      {errors[field.name]}
                    </p>
                  )}
                </div>
              ))}

              {submitError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{submitError}</p>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-100">
                <Link to="/occupants">
                  <Button type="button" variant="ghost">Cancel</Button>
                </Link>
                <Button type="submit" disabled={loading}>
                  {loading ? 'Saving...' : isEditing ? 'Save Changes' : 'Add Occupant'}
                </Button>
              </div>
            </div>
          </form>
        </Card>
      </div>
    </PageContainer>
  )
}
