import { useState, useEffect, useCallback } from 'react'
import { backupService } from '../services/backup'

export function useBackups(params = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await backupService.list(params)
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [JSON.stringify(params)])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useBackup(id) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const result = await backupService.get(id)
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { fetch() }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useBackupAction() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const create = async (notes = '') => {
    setLoading(true)
    setError(null)
    try {
      const result = await backupService.create({ notes })
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const restore = async (id, confirm = true) => {
    setLoading(true)
    setError(null)
    try {
      const result = await backupService.restore(id, { backup_id: id, confirm })
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  const validate = async (id) => {
    setLoading(true)
    setError(null)
    try {
      const result = await backupService.validate(id)
      return result
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { create, restore, validate, loading, error }
}
