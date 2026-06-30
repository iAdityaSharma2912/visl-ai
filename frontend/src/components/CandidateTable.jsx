import React from 'react'

const statusLabels = {
  uploaded: 'Uploaded',
  evaluated: 'Evaluated',
  shortlisted: 'Shortlisted',
  tested: 'Tested',
  interview_scheduled: 'Interview scheduled',
}

const statusStyles = {
  uploaded: 'bg-line/60 text-ink/60',
  evaluated: 'bg-amber-100 text-amber-800',
  shortlisted: 'bg-blue-100 text-blue-800',
  tested: 'bg-purple-100 text-purple-800',
  interview_scheduled: 'bg-moss/15 text-moss',
}

export default function CandidateTable({ candidates }) {
  const [expanded, setExpanded] = React.useState(null)

  if (!candidates.length) {
    return (
      <div className="text-sm text-ink/40 py-8 text-center border border-dashed border-line rounded-lg">
        No candidates yet. Upload a dataset to begin.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-ink/50 step-num text-xs uppercase tracking-wide border-b border-line">
            <th className="py-2 pr-3">Rank</th>
            <th className="py-2 pr-3">#</th>
            <th className="py-2 pr-3">Name</th>
            <th className="py-2 pr-3">JD Match</th>
            <th className="py-2 pr-3">GitHub</th>
            <th className="py-2 pr-3">Test</th>
            <th className="py-2 pr-3">Final</th>
            <th className="py-2 pr-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, idx) => (
            <React.Fragment key={c.id}>
              <tr
                className="border-b border-line/60 hover:bg-white/50 cursor-pointer"
                onClick={() => setExpanded(expanded === c.id ? null : c.id)}
              >
                <td className="py-2 pr-3 step-num text-ink/40">{idx + 1}</td>
                <td className="py-2 pr-3 step-num text-ink/40">{c.s_no}</td>
                <td className="py-2 pr-3 font-medium">{c.name}</td>
                <td className="py-2 pr-3">{c.jd_score ?? '—'}</td>
                <td className="py-2 pr-3">{c.github_score ?? '—'}</td>
                <td className="py-2 pr-3">
                  {c.test_la_score != null ? `${c.test_la_score}/${c.test_code_score}` : '—'}
                </td>
                <td className="py-2 pr-3 font-semibold text-moss">{c.final_score ?? '—'}</td>
                <td className="py-2 pr-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs ${statusStyles[c.status] || ''}`}>
                    {statusLabels[c.status] || c.status}
                  </span>
                </td>
              </tr>
              {expanded === c.id && c.explanation && (
                <tr className="bg-white/40">
                  <td colSpan={8} className="px-3 py-3 text-ink/70 text-xs leading-relaxed">
                    {c.explanation}
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}
