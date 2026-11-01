export const BENCHMARK_CANDIDATES = [
  {
    id: 'koramangala-5th-block',
    name: 'Koramangala 5th Block',
    lat: 12.9352,
    lon: 77.6245,
    competitor_count: 18,
    anchor_count: 24,
    avg_rent_per_sqft: 130,
    accessibility_score: 0.85,
  },
  {
    id: 'indiranagar-100ft-road',
    name: 'Indiranagar 100ft Rd',
    lat: 12.9719,
    lon: 77.6412,
    competitor_count: 26,
    anchor_count: 32,
    avg_rent_per_sqft: 165,
    accessibility_score: 0.9,
  },
  {
    id: 'hsr-layout-sector-1',
    name: 'HSR Layout Sector 1',
    lat: 12.9116,
    lon: 77.6389,
    competitor_count: 12,
    anchor_count: 19,
    avg_rent_per_sqft: 95,
    accessibility_score: 0.78,
  },
  {
    id: 'jayanagar-4th-block',
    name: 'Jayanagar 4th Block',
    lat: 12.9299,
    lon: 77.5834,
    competitor_count: 8,
    anchor_count: 15,
    avg_rent_per_sqft: 85,
    accessibility_score: 0.75,
  },
]

export const DEFAULT_BUSINESS_INPUTS = {
  monthly_rent: 65_000,
  other_monthly_fixed_costs: 45_000,
  average_ticket_size: 280,
  variable_cost_per_cover: 95,
  seats: 28,
  operating_hours_per_day: 12,
  seat_turnovers_per_hour: 0.75,
  operating_days_per_month: 30,
  expected_covers_per_day: 110,
  initial_working_capital: 350_000,
}

export const DEFAULT_CRITERIA = [
  { name: 'competitor_count', weight: 0.25, is_benefit: false },
  { name: 'anchor_count', weight: 0.3, is_benefit: true },
  { name: 'avg_rent_per_sqft', weight: 0.25, is_benefit: false },
  { name: 'accessibility_score', weight: 0.2, is_benefit: true },
]

export const DEFAULT_SELECTED_SITE = {
  lat: BENCHMARK_CANDIDATES[0].lat,
  lon: BENCHMARK_CANDIDATES[0].lon,
}
