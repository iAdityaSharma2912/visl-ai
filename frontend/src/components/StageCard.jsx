import React from 'react'

export default function StageCard({ number, title, description, status, children }) {
  const statusColors = {
    idle: 'border-line text-ink/40',
    active: 'border-moss text-moss',
    done: 'border-moss2 text-moss2',
  }

  return (
    <div className="relative pl-12 pb-10 border-l-2 border-line last:border-transparent last:pb-0">
      <div
        className={`absolute -left-[17px] top-0 w-8 h-8 rounded-full bg-paper border-2 flex items-center justify-center step-num text-xs font-medium ${statusColors[status] || statusColors.idle}`}
      >
        {number}
      </div>
      <div className="bg-white/60 border border-line rounded-lg p-5">
        <div className="flex items-baseline justify-between mb-1">
          <h3 className="font-display text-lg text-ink">{title}</h3>
          {status === 'done' && (
            <span className="text-xs step-num text-moss2 uppercase tracking-wide">complete</span>
          )}
        </div>
        <p className="text-sm text-ink/60 mb-4">{description}</p>
        {children}
      </div>
    </div>
  )
}
