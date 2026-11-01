import { Activity, Coffee, Wifi, WifiOff } from 'lucide-react'

const HEALTH_LABELS = {
  checking: 'Connecting',
  online: 'Backend online',
  offline: 'Backend offline',
}

export function Header({ health }) {
  const isOnline = health === 'online'
  const isChecking = health === 'checking'

  return (
    <header className="topbar">
      <a className="brand" href="/" aria-label="Groundwork home">
        <span className="brand-mark"><Coffee size={20} strokeWidth={2.2} /></span>
        <span className="brand-name">groundwork<span>.</span></span>
      </a>
      <div className="header-center">
        <span className="header-title">Spatial-Financial Decision Support System</span>
        <span className="header-subtitle">LOCATION INTELLIGENCE FOR INDEPENDENT CAFÉS</span>
      </div>
      <div className={`backend-status ${isOnline ? 'online' : isChecking ? 'checking' : 'offline'}`} role="status">
        <span className="status-indicator">
          {isOnline ? <Wifi size={14} /> : isChecking ? <Activity size={14} /> : <WifiOff size={14} />}
        </span>
        <span>{HEALTH_LABELS[health] ?? HEALTH_LABELS.offline}</span>
      </div>
    </header>
  )
}
