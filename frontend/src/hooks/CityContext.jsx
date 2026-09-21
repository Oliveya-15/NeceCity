import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../services/api'

const CityContext = createContext(null)

const STORAGE_KEY = 'nececity.selectedCitySlug'

export function CityProvider({ children }) {
  const [cities, setCities] = useState([])
  const [selectedCityId, setSelectedCityId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .listCities()
      .then((list) => {
        setCities(list)
        if (list.length > 0) {
          const savedSlug = localStorage.getItem(STORAGE_KEY)
          const saved = list.find((c) => c.slug === savedSlug)
          setSelectedCityId((saved || list[0]).id)
        }
      })
      .catch((err) => setError(err))
      .finally(() => setLoading(false))
  }, [])

  const selectedCity = useMemo(() => cities.find((c) => c.id === selectedCityId) || null, [cities, selectedCityId])

  function selectCity(id) {
    setSelectedCityId(id)
    const city = cities.find((c) => c.id === id)
    if (city) localStorage.setItem(STORAGE_KEY, city.slug)
  }

  const value = { cities, selectedCity, selectedCityId, selectCity, loading, error }
  return <CityContext.Provider value={value}>{children}</CityContext.Provider>
}

export function useCity() {
  const ctx = useContext(CityContext)
  if (!ctx) throw new Error('useCity must be used within a CityProvider')
  return ctx
}
