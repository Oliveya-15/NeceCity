import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Wraps an async fetch function with loading/error/data state so every
 * page handles the same four states consistently (loading, error, empty,
 * success) rather than each page reinventing this.
 *
 * `deps` follows the same rules as useEffect's dependency array - the
 * fetch re-runs when any dependency changes (e.g. the selected city id).
 */
export function useApi(fetchFn, deps = [], { skip = false } = {}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(!skip)
  const [error, setError] = useState(null)
  const requestId = useRef(0)

  const load = useCallback(() => {
    if (skip) return
    const currentRequest = ++requestId.current
    setLoading(true)
    setError(null)
    fetchFn()
      .then((result) => {
        if (currentRequest === requestId.current) setData(result)
      })
      .catch((err) => {
        if (currentRequest === requestId.current) setError(err)
      })
      .finally(() => {
        if (currentRequest === requestId.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    load()
  }, [load])

  return { data, loading, error, reload: load }
}
