import { AlertTriangle, Info, ShieldAlert } from 'lucide-react'

const SEVERITY = {
  CRITICAL: { label: 'Critical', icon: ShieldAlert, className: 'critical' },
  WARNING: { label: 'Warning', icon: AlertTriangle, className: 'warning' },
  INFO: { label: 'Info', icon: Info, className: 'info' },
}

function formatMeasuredValue(value, ruleName) {
  if (value === null || value === undefined) return 'Not finite'
  if (['RENTAL_STRESS', 'LOW_CONTRIBUTION_MARGIN'].includes(ruleName)) {
    return `${(value * 100).toFixed(1)}%`
  }
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(value)
}

export function RiskCards({ assessment }) {
  const flags = assessment?.flags ?? []

  return (
    <section className="risk-section">
      <div className="subsection-heading">
        <div><div className="eyebrow">DIAGNOSTICS</div><h3>What needs attention</h3></div>
        <span className="flag-count">{flags.length} {flags.length === 1 ? 'flag' : 'flags'}</span>
      </div>
      {flags.length === 0 ? (
        <div className="no-flags"><ShieldAlert size={17} /><span>No diagnostic thresholds triggered for these assumptions.</span></div>
      ) : (
        <div className="risk-list">
          {flags.map((flag, index) => {
            const severity = SEVERITY[flag.severity] ?? SEVERITY.INFO
            const Icon = severity.icon
            return (
              <article className={`risk-card ${severity.className}`} key={`${flag.rule_name}-${index}`}>
                <span className="risk-icon"><Icon size={17} /></span>
                <div className="risk-content">
                  <div className="risk-title-row">
                    <strong>{flag.rule_name.replaceAll('_', ' ')}</strong>
                    <span className="risk-severity">{severity.label}</span>
                  </div>
                  <p>{flag.plain_language_explanation}</p>
                  <span className="risk-measured">
                    Measured: {formatMeasuredValue(flag.measured_value, flag.rule_name)}
                    {flag.threshold !== null && flag.threshold !== undefined
                      ? ` · Threshold: ${formatMeasuredValue(flag.threshold, flag.rule_name)}`
                      : ''}
                  </span>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
