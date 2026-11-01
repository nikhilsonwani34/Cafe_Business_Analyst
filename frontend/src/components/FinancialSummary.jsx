import {
  Banknote,
  Gauge,
  Hourglass,
  ShoppingBag,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value)
}

function formatNumber(value) {
  return value === null || value === undefined ? 'N/A' : value.toFixed(1)
}

export function FinancialSummary({ financial }) {
  const profit = financial.projected_monthly_operating_profit
  const metrics = [
    {
      label: 'Contribution margin',
      value: financial.contribution_margin_ratio === null
        ? 'N/A'
        : `${(financial.contribution_margin_ratio * 100).toFixed(1)}%`,
      note: 'Per-cover contribution',
      icon: Gauge,
      tone: financial.contribution_margin_ratio !== null && financial.contribution_margin_ratio < 0.5 ? 'warning' : 'green',
    },
    {
      label: 'Daily break-even',
      value: formatNumber(financial.break_even_covers_per_day),
      note: 'Covers required / day',
      icon: ShoppingBag,
      tone: financial.break_even_within_capacity ? 'green' : 'warning',
    },
    {
      label: 'Maximum capacity',
      value: formatNumber(financial.maximum_covers_per_day),
      note: 'Modeled covers / day',
      icon: Hourglass,
      tone: 'neutral',
    },
    {
      label: 'Monthly operating result',
      value: formatCurrency(profit),
      note: profit >= 0 ? 'Projected operating profit' : 'Projected operating loss',
      icon: profit >= 0 ? TrendingUp : TrendingDown,
      tone: profit >= 0 ? 'green' : 'warning',
    },
    {
      label: 'Cash runway',
      value: financial.cash_runway_months === null ? 'Sustainable*' : `${financial.cash_runway_months.toFixed(1)} mo`,
      note: financial.cash_runway_months === null ? 'No modeled monthly cash burn' : 'At projected monthly burn',
      icon: Banknote,
      tone: financial.cash_runway_months !== null && financial.cash_runway_months < 3 ? 'warning' : 'neutral',
    },
  ]

  return (
    <>
      <div className="metric-grid">
        {metrics.map((metric) => {
          const Icon = metric.icon
          return (
            <article className={`metric-card tone-${metric.tone}`} key={metric.label}>
              <div className="metric-top"><span>{metric.label}</span><Icon size={16} /></div>
              <strong className="metric-value">{metric.value}</strong>
              <span className="metric-note">{metric.note}</span>
            </article>
          )
        })}
      </div>
      {financial.cash_runway_months === null && (
        <p className="footnote">* The current model reports no runway depletion when projected operations are profitable or break even.</p>
      )}
    </>
  )
}
