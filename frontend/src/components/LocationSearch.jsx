import { useEffect, useRef, useState } from 'react'
import { LoaderCircle, MapPin, Search, X } from 'lucide-react'

// OpenStreetMap's free place search. Its usage policy allows light, user-triggered
// searches (one request per submit, never per keystroke), which is how this works.
const SEARCH_URL = 'https://nominatim.openstreetmap.org/search'

// Accepts "22.7196, 75.8577", "22.7196 75.8577" or "-33.87,151.21".
const COORDINATE_PATTERN = /^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$/

function parseCoordinates(text) {
  const match = COORDINATE_PATTERN.exec(text)
  if (!match) return null
  const lat = Number(match[1])
  const lon = Number(match[2])
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null
  return { lat, lon }
}

function shortName(displayName) {
  return displayName.split(',').slice(0, 2).join(',').trim()
}

export function LocationSearch({ onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [state, setState] = useState('idle') // idle | loading | done | error
  const [message, setMessage] = useState('')
  const controllerRef = useRef(null)

  useEffect(() => () => controllerRef.current?.abort(), [])

  const reset = () => {
    controllerRef.current?.abort()
    setResults([])
    setState('idle')
    setMessage('')
  }

  const choose = (site, label) => {
    onSelect({ lat: site.lat, lon: site.lon })
    reset()
    if (label) setQuery(label)
  }

  const search = async (event) => {
    event.preventDefault()
    const text = query.trim()
    if (!text) return

    const coordinates = parseCoordinates(text)
    if (coordinates) {
      choose(coordinates)
      return
    }

    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setState('loading')
    setResults([])
    setMessage('')

    try {
      const params = new URLSearchParams({
        q: text,
        format: 'jsonv2',
        limit: '5',
        'accept-language': 'en',
      })
      const response = await fetch(`${SEARCH_URL}?${params}`, { signal: controller.signal })
      if (!response.ok) throw new Error(String(response.status))

      const places = await response.json()
      const found = places
        .map((place) => ({
          id: place.place_id,
          name: place.display_name,
          lat: Number(place.lat),
          lon: Number(place.lon),
        }))
        .filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lon))

      setResults(found)
      setState('done')
      setMessage(found.length ? '' : 'No places found. Try adding the city or a nearby landmark.')
    } catch (searchError) {
      if (searchError.name === 'AbortError') return
      setState('error')
      setMessage(
        searchError.message === '429'
          ? 'Search is busy right now. Wait a few seconds and try again.'
          : 'Could not search places right now. You can still click the map or use your location.',
      )
    }
  }

  const clear = () => {
    setQuery('')
    reset()
  }

  return (
    <form className="location-search" onSubmit={search} role="search">
      <label className="sr-only" htmlFor="location-search-input">Search for a place</label>
      <div className="location-search-field">
        <Search size={14} />
        <input
          id="location-search-input"
          type="text"
          value={query}
          placeholder="Search a place, or paste coordinates like 22.7196, 75.8577"
          autoComplete="off"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') reset()
          }}
        />
        {query && (
          <button className="location-search-clear" type="button" onClick={clear} aria-label="Clear search">
            <X size={13} />
          </button>
        )}
        <button className="location-search-submit" type="submit" disabled={state === 'loading' || !query.trim()}>
          {state === 'loading' ? <LoaderCircle className="spin" size={13} /> : 'Search'}
        </button>
      </div>

      {results.length > 0 && (
        <ul className="location-search-results">
          {results.map((place) => (
            <li key={place.id}>
              <button type="button" onClick={() => choose(place, shortName(place.name))}>
                <MapPin size={13} />
                <span>{place.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {message && (
        <p className={`location-search-message ${state === 'error' ? 'is-warn' : ''}`} role="status">
          {message}
        </p>
      )}
    </form>
  )
}
