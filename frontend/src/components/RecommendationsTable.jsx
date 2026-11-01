import { ArrowDownRight, ArrowUpRight, MapPinned, Trophy } from 'lucide-react'

function formatScore(score) {
  return `${(score * 100).toFixed(1)}%`
}

export function RecommendationsTable({ recommendation }) {
  const candidates = recommendation?.ranked_candidates ?? []

  return (
    <section className="panel recommendations-panel">
      <div className="panel-heading">
        <div>
          <div className="eyebrow">RELATIVE LOCATION COMPARISON</div>
          <h2>Alternative micro-markets</h2>
        </div>
        <span className="topsis-tag">TOPSIS</span>
      </div>
      <p className="table-intro">
        A relative ranking across the supplied criteria and weights—not a success probability.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Location</th>
              <th>Closeness</th>
              <th>Trade-off explanation</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((item) => (
              <tr key={item.candidate.id}>
                <td>
                  <span className={`rank-badge ${item.rank === 1 ? 'top-rank' : ''}`}>
                    {item.rank === 1 ? <Trophy size={13} /> : `0${item.rank}`}
                  </span>
                </td>
                <td>
                  <span className="location-name"><MapPinned size={14} />{item.candidate.name}</span>
                  <span className="location-subline">
                    {item.candidate.competitor_count} competitors · {item.candidate.anchor_count} anchors
                  </span>
                </td>
                <td>
                  <strong className="score-value">{formatScore(item.score)}</strong>
                  <span className="score-track"><i style={{ width: `${item.score * 100}%` }} /></span>
                </td>
                <td>
                  <p className="tradeoff-summary">{item.trade_off_explanation.summary}</p>
                  {item.trade_off_explanation.compared_candidate_id && (
                    <div className="tradeoff-tags">
                      {item.trade_off_explanation.advantages.map((advantage) => (
                        <span className="tradeoff-tag advantage" key={`adv-${advantage.criterion_name}`}>
                          <ArrowUpRight size={12} /> {advantage.criterion_name.replaceAll('_', ' ')}
                        </span>
                      ))}
                      {item.trade_off_explanation.disadvantages.map((disadvantage) => (
                        <span className="tradeoff-tag disadvantage" key={`dis-${disadvantage.criterion_name}`}>
                          <ArrowDownRight size={12} /> {disadvantage.criterion_name.replaceAll('_', ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="source-note">Candidate figures are illustrative UI benchmark inputs, not verified current market measurements.</p>
    </section>
  )
}
