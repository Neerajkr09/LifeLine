import { useCallback, useState } from 'react'

/**
 * Wraps navigator.geolocation.getCurrentPosition in a promise-friendly hook.
 * Used wherever the platform needs precise coordinates: registration (once,
 * optionally) and blood request submission (mandatory).
 */
export function useGeolocation() {
  const [coordinates, setCoordinates] = useState(null)
  const [status, setStatus] = useState('idle') // idle | requesting | granted | denied | unsupported | error
  const [error, setError] = useState(null)

  const requestLocation = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        setStatus('unsupported')
        const err = new Error('Geolocation is not supported by this browser.')
        setError(err)
        reject(err)
        return
      }

      setStatus('requesting')
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          }
          setCoordinates(coords)
          setStatus('granted')
          setError(null)
          resolve(coords)
        },
        (geoError) => {
          setStatus(geoError.code === geoError.PERMISSION_DENIED ? 'denied' : 'error')
          setError(geoError)
          reject(geoError)
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
      )
    })
  }, [])

  return { coordinates, status, error, requestLocation }
}
