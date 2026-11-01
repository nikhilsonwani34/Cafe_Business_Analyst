import { useState } from 'react'
import {
  ArrowRight,
  Banknote,
  ChevronDown,
  CircleDollarSign,
  Coffee,
  LoaderCircle,
  RotateCcw,
  Settings2,
  Users,
} from 'lucide-react'
import { DEFAULT_BUSINESS_INPUTS } from '../data/presets'

const PRIMARY_FIELDS = [
  {
    key: 'monthly_rent',
    label: 'Monthly rent',
    min: 0,
    max: 250_000,
    step: 5_000,
    icon: Banknote,
    hint: '₹ / month',
  },
  {
    key: 'average_ticket_size',
    label: 'Average ticket',
    min: 80,
    max: 1_000,
    step: 10,
    icon: CircleDollarSign,
    hint: '₹ / cover',
  },
  {
    key: 'seats',
    label: 'Seating capacity',
    min: 4,
    max: 120,
    step: 1,
    icon: Users,
    hint: 'seats',
  },
  {
    key: 'initial_working_capital',
    label: 'Working capital',
    min: 0,
    max: 2_000_000,
    step: 25_000,
    icon: Banknote,
    hint: '₹ available',
  },
]

const SECONDARY_FIELDS = [
  { key: 'other_monthly_fixed_costs', label: 'Other monthly fixed costs (₹)', min: 0 },
  { key: 'variable_cost_per_cover', label: 'Variable cost per cover (₹)', min: 0 },
  { key: 'expected_covers_per_day', label: 'Expected covers / day', min: 0 },
  { key: 'operating_hours_per_day', label: 'Operating hours / day', min: 1 },
  { key: 'seat_turnovers_per_hour', label: 'Seat turns per hour', min: 0.1, step: 0.05 },
]

function formatInputValue(value) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value)
}

function RangeField({ field, value, onChange }) {
  const Icon = field.icon

  return (
    <div className="range-field">
      <div className="range-heading">
        <label htmlFor={field.key}><Icon size={16} />{field.label}</label>
        <span className="range-value">{formatInputValue(value)} <small>{field.hint}</small></span>
      </div>
      <input
        id={field.key}
        type="range"
        min={field.min}
        max={field.max}
        step={field.step}
        value={Math.min(value, field.max)}
        onChange={(event) => onChange(field.key, Number(event.target.value))}
        aria-label={field.label}
      />
      <div className="range-limits"><span>{formatInputValue(field.min)}</span><span>{formatInputValue(field.max)}</span></div>
      <input
        className="sr-only"
        type="number"
        min={field.min}
        max={field.max}
        step={field.step}
        value={value}
        onChange={(event) => onChange(field.key, Number(event.target.value))}
        aria-label={`Exact ${field.label}`}
      />
    </div>
  )
}

export function BusinessForm({ value, onChange, onSubmit, isLoading }) {
  const [showDetails, setShowDetails] = useState(false)
  const update = (key, nextValue) => onChange((current) => ({ ...current, [key]: nextValue }))

  const reset = () => {
    onChange(DEFAULT_BUSINESS_INPUTS)
    setShowDetails(false)
  }

  return (
    <section className="panel form-panel">
      <div className="panel-heading form-heading">
        <div>
          <div className="eyebrow">YOUR BUSINESS PLAN</div>
          <h2>Set your assumptions</h2>
        </div>
        <button className="text-button" onClick={reset} type="button" title="Reset to example assumptions">
          <RotateCcw size={14} /> Reset
        </button>
      </div>

      <div className="assumptions-badge"><Coffee size={14} /> Independent café · Monthly model</div>
      <div className="range-stack">
        {PRIMARY_FIELDS.map((field) => (
          <RangeField
            key={field.key}
            field={field}
            value={value[field.key]}
            onChange={update}
          />
        ))}
      </div>

      <button
        className="details-toggle"
        type="button"
        onClick={() => setShowDetails((current) => !current)}
        aria-expanded={showDetails}
      >
        <span><Settings2 size={15} /> Operating assumptions</span>
        <ChevronDown className={showDetails ? 'rotated' : ''} size={16} />
      </button>
      {showDetails && (
        <div className="secondary-fields">
          {SECONDARY_FIELDS.map((field) => (
            <label className="secondary-field" key={field.key}>
              <span>{field.label}</span>
              <input
                type="number"
                min={field.min}
                step={field.step ?? 1}
                value={value[field.key]}
                onChange={(event) => update(field.key, Number(event.target.value))}
              />
            </label>
          ))}
        </div>
      )}

      <div className="capital-note">
        <span className="capital-icon"><Banknote size={16} /></span>
        <span>One-time setup costs should already be deducted from working capital.</span>
      </div>
      <button className="primary-button" type="button" onClick={onSubmit} disabled={isLoading}>
        {isLoading ? <LoaderCircle className="spin" size={18} /> : <span>Run feasibility analysis</span>}
        {!isLoading && <ArrowRight size={17} />}
      </button>
      <p className="form-disclaimer">Assumptions are yours to adjust. Outputs are scenario estimates, not guarantees.</p>
    </section>
  )
}
