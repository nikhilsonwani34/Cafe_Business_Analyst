import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Compass,
  LoaderCircle,
  LocateFixed,
  MapPin,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { BusinessForm } from './components/BusinessForm'
import { FinancialSummary } from './components/FinancialSummary'
import { Header } from './components/Header'
import { LocationSearch } from './components/LocationSearch'
import { MapView } from './components/MapView'
import { RecommendationsTable } from './components/RecommendationsTable'
import { RiskCards } from './components/RiskCards'
import {
  BENCHMARK_CANDIDATES,
  DEFAULT_BUSINESS_INPUTS,
  DEFAULT_CRITERIA,
  DEFAULT_SELECTED_SITE,
} from './data/presets'
import './App.css'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
const API_ORIGIN = import.meta.env.VITE_API_BASE_URL
  ? new URL(import.meta.env.VITE_API_BASE_URL).origin
  : ''
const HEALTH_URL = `${API_ORIGIN}/health`

function makeSpatialRequest({ lat, lon }) {
  const latitudeDelta = 0.025
  const longitudeDelta = 0.025

  return {
    latitude: lat,
    longitude: lon,
    bounding_box: {
      south: Math.max(-90, lat - latitudeDelta),
      west: Math.max(-180, lon - longitudeDelta),
      north: Math.min(90, lat + latitudeDelta),
      east: Math.min(180, lon + longitudeDelta),
    },
    radii_meters: [500, 1000],
  }
}

const GEOLOCATION_OPTIONS = { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 }

const LOCATION_MESSAGES = {
  locating: 'Finding your device location…',
  granted: 'Using your device location.',
  denied: 'Location permission was denied, so the default site is shown. Click the map to choose a site, or allow location access and try again.',
  unavailable: 'Your device could not determine its position, so the default site is shown.',
  timeout: 'Finding your location timed out, so the default site is shown.',
  unsupported: 'This browser does not support device location, so the default site is shown.',
  insecure: 'Device location only works on https:// or localhost, so the default site is shown.',
}

function App() {
  const [business, setBusiness] = useState(DEFAULT_BUSINESS_INPUTS)
  const [selectedSite, setSelectedSite] = useState(DEFAULT_SELECTED_SITE)
  const [locationStatus, setLocationStatus] = useState('idle')
  const [health, setHealth] = useState('checking')
  const [result, setResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const hasPickedManually = useRef(false)

  const candidates = BENCHMARK_CANDIDATES

  const locateDevice = useCallback(({ force = false } = {}) => {
    if (!window.isSecureContext) {
      setLocationStatus('insecure')
      return
    }
    if (!('geolocation' in navigator)) {
      setLocationStatus('unsupported')
      return
    }

    setLocationStatus('locating')
    navigator.geolocation.getCurrentPosition(
      (position) => {
        // Never override a site the user already chose by hand while we were waiting,
        // unless they explicitly pressed "Use my location".
        if (hasPickedManually.current && !force) {
          setLocationStatus('idle')
          return
        }
        hasPickedManually.current = false
        setSelectedSite({ lat: position.coords.latitude, lon: position.coords.longitude })
        setLocationStatus('granted')
      },
      (geoError) => {
        if (geoError.code === geoError.PERMISSION_DENIED) setLocationStatus('denied')
        else if (geoError.code === geoError.TIMEOUT) setLocationStatus('timeout')
        else setLocationStatus('unavailable')
      },
      GEOLOCATION_OPTIONS,
    )
  }, [])

  // Ask the device for its position once, when the app first opens.
  useEffect(() => {
    const timer = window.setTimeout(() => locateDevice(), 0)
    return () => window.clearTimeout(timer)
  }, [locateDevice])

  const chooseSite = useCallback((site) => {
    hasPickedManually.current = true
    setSelectedSite(site)
    setLocationStatus('idle')
  }, [])

  const checkHealth = useCallback(async (signal) => {
    try {
      const response = await fetch(HEALTH_URL, { signal })
      if (!response.ok) {
        setHealth('offline')
        return
      }
      const payload = await response.json()
      setHealth(payload.status === 'healthy' ? 'online' : 'offline')
    } catch (healthError) {
      if (healthError.name !== 'AbortError') setHealth('offline')
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const initialCheck = window.setTimeout(
      () => checkHealth(controller.signal),
      0,
    )
    const timer = window.setInterval(() => checkHealth(), 30_000)
    return () => {
      controller.abort()
      window.clearTimeout(initialCheck)
      window.clearInterval(timer)
    }
  }, [checkHealth])

  const analyze = async () => {
    setIsLoading(true)
    setError('')
    setResult(null)

    const payload = {
      business,
      selected_site: makeSpatialRequest(selectedSite),
      alternative_candidates: candidates,
      criteria: DEFAULT_CRITERIA,
    }

    try {
      const response = await fetch(`${API_BASE_URL}/v1/feasibility/full`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const responseBody = await response.json().catch(() => null)

      if (!response.ok) {
        const detail = responseBody?.detail
        const message = Array.isArray(detail)
          ? detail.map((item) => item.msg).join('; ')
          : detail
        throw new Error(message || `Analysis failed with HTTP ${response.status}`)
      }

      setResult(responseBody)
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? 'Could not reach the DSS backend. Check that FastAPI is running at http://localhost:8000.'
          : requestError.message,
      )
    } finally {
      setIsLoading(false)
    }
  }

  const selectCandidate = (candidate) => {
    chooseSite({ lat: candidate.lat, lon: candidate.lon })
  }

  return (
    <div className="app-shell">
      <Header health={health} />

      <main className="dashboard">
        <section className="intro-row">
          <div>
            <div className="eyebrow"><Sparkles size={14} /> PRE-LAUNCH PLANNING WORKSPACE</div>
            <h1>Find the signal<br /><span>before you sign.</span></h1>
            <p className="intro-copy">
              Stress-test café economics and explore location context with transparent,
              assumption-led analysis.
            </p>
          </div>
          <div className="intro-note">
            <ShieldCheck size={20} />
            <div>
              <strong>Decision support, not prediction</strong>
              <span>Every metric is tied to visible inputs and explainable rules.</span>
            </div>
          </div>
        </section>

        <div className="workspace-grid">
          <aside className="controls-column">
            <BusinessForm
              value={business}
              onChange={setBusiness}
              onSubmit={analyze}
              isLoading={isLoading}
            />
            {error && (
              <div className="error-banner" role="alert">
                <Activity size={18} />
                <div><strong>Analysis unavailable</strong><span>{error}</span></div>
                <button className="icon-button" onClick={analyze} aria-label="Retry analysis">
                  <RefreshCw size={16} />
                </button>
              </div>
            )}
          </aside>

          <section className="results-column">
            <section className="panel map-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">SITE EXPLORER</div>
                  <h2>Choose a proposed location</h2>
                </div>
                <div className="location-actions">
                  <button
                    className="locate-button"
                    type="button"
                    onClick={() => locateDevice({ force: true })}
                    disabled={locationStatus === 'locating'}
                    title="Set the proposed site to this device's current location"
                  >
                    {locationStatus === 'locating'
                      ? <LoaderCircle className="spin" size={14} />
                      : <LocateFixed size={14} />}
                    Use my location
                  </button>
                  <div className="location-chip">
                    <MapPin size={15} />
                    {selectedSite.lat.toFixed(4)}, {selectedSite.lon.toFixed(4)}
                  </div>
                </div>
              </div>
              <LocationSearch onSelect={chooseSite} />
              <MapView
                candidates={candidates}
                selectedSite={selectedSite}
                onLocationChange={chooseSite}
                onCandidateSelect={selectCandidate}
              />
              <div className="map-legend">
                <span><i className="legend-dot selected" /> Proposed site</span>
                <span><i className="legend-dot candidate" /> Benchmark locations</span>
                <span><i className="legend-ring" /> 500 m / 1 km radial buffers</span>
              </div>
              <p className="map-hint"><Compass size={14} /> Search a place, click the map, or drag the pin to change the proposed site.</p>
              {LOCATION_MESSAGES[locationStatus] && (
                <p
                  className={`location-status ${locationStatus === 'granted' ? 'is-ok' : locationStatus === 'locating' ? '' : 'is-warn'}`}
                  role="status"
                >
                  <LocateFixed size={14} /> {LOCATION_MESSAGES[locationStatus]}
                </p>
              )}
            </section>

            <section className="section-block">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">FINANCIAL REALITY CHECK</div>
                  <h2>Can the numbers work?</h2>
                </div>
                {result && (
                  <span className="updated-label">
                    <span className="live-dot" /> ANALYSIS COMPLETE
                  </span>
                )}
              </div>
              {result ? (
                <>
                  <FinancialSummary financial={result.financial} />
                  {result.financial.break_even_covers_per_day !== null && (
                    <div className={`capacity-callout ${result.financial.break_even_within_capacity ? 'is-safe' : 'is-risk'}`}>
                      {result.financial.break_even_within_capacity
                        ? <ArrowUpRight size={17} />
                        : <ArrowDownRight size={17} />}
                      <span>
                        {result.financial.break_even_within_capacity
                          ? `Break-even is within modeled capacity: ${result.financial.break_even_covers_per_day.toFixed(1)} required covers/day against ${result.financial.maximum_covers_per_day.toFixed(1)} maximum.`
                          : `Capacity gap: break-even requires ${result.financial.break_even_covers_per_day.toFixed(1)} covers/day, above ${result.financial.maximum_covers_per_day.toFixed(1)} modeled maximum.`}
                      </span>
                    </div>
                  )}
                  <RiskCards assessment={result.risk_assessment} />
                </>
              ) : (
                <div className="empty-state">
                  <div className="empty-icon"><Activity size={22} /></div>
                  <strong>{isLoading ? 'Running the feasibility pipeline…' : 'Your analysis will appear here'}</strong>
                  <span>
                    {isLoading
                      ? 'Checking financial assumptions, nearby OSM points of interest, and candidate trade-offs.'
                      : 'Adjust the assumptions and run an analysis to see break-even, runway, risk flags, and location comparisons.'}
                  </span>
                  {isLoading && <div className="loading-bar"><i /></div>}
                </div>
              )}
            </section>

            {result && (
              <>
                <section className="section-block spatial-result">
                  <div className="section-heading">
                    <div>
                      <div className="eyebrow">LOCAL CONTEXT</div>
                      <h2>Mapped points of interest</h2>
                    </div>
                    <span className="cache-label">{result.spatial.cache_status === 'hit' ? 'CACHED DATA' : 'LIVE OSM QUERY'}</span>
                  </div>
                  <div className="spatial-metrics">
                    {result.spatial.summaries.map((summary) => (
                      <div className="spatial-metric" key={summary.radius_meters}>
                        <span>WITHIN {(summary.radius_meters / 1000).toLocaleString('en-IN')} KM</span>
                        <strong>{summary.competitor_count}<small> competitors</small></strong>
                        <strong>{summary.demand_anchor_count}<small> anchors</small></strong>
                      </div>
                    ))}
                  </div>
                  <p className="source-note">
                    {result.spatial.attribution} · {result.spatial.license} · POI counts are mapped proxies, not measured footfall.
                  </p>
                </section>
                <RecommendationsTable recommendation={result.recommendation} />
              </>
            )}

            {!result && !isLoading && (
              <div className="preflight-row">
                <span><MapPin size={16} /> OpenStreetMap POI context</span>
                <span><Activity size={16} /> Deterministic CVP model</span>
                <span><ShieldCheck size={16} /> Explainable risk rules</span>
              </div>
            )}
          </section>
        </div>
      </main>
      <footer className="app-footer">
        <span>SPATIAL-FINANCIAL DSS</span>
        <span>Estimates depend on user assumptions and mapped data coverage.</span>
        <span>Built for clearer decisions, not guarantees.</span>
      </footer>
      <div className="sr-only" aria-live="polite">
        {health === 'online' ? 'Backend connected' : health === 'offline' ? 'Backend unreachable' : 'Checking backend'}
      </div>
    </div>
  )
}

export default App
