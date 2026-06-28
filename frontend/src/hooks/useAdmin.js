import { useState, useEffect, useCallback } from 'react'
import { adminService } from '../services/admin'

function useFetch(fetchFn, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetchFn()
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useAdminProperties() {
  return useFetch(() => adminService.propertiesList(), [])
}

export function useAdminSections(propertyId) {
  return useFetch(() => adminService.sectionsList({ property_id: propertyId }), [propertyId])
}

export function useAdminUnits(params = {}) {
  return useFetch(() => adminService.unitsList(params), [JSON.stringify(params)])
}

export function usePricingRules(params = {}) {
  return useFetch(() => adminService.pricingRulesList(params), [JSON.stringify(params)])
}

export function useAdminUsers() {
  return useFetch(() => adminService.usersList(), [])
}

export function useAdminGroups() {
  return useFetch(() => adminService.userGroups(), [])
}
