export default function StatCard({ label, value, icon: Icon, accent = 'teal', hint }) {
  const accentClasses = {
    teal: 'bg-teal-50 text-teal-600',
    crimson: 'bg-crimson-50 text-crimson-600',
    ink: 'bg-ink-100 text-ink-600',
  }[accent]

  return (
    <div className="bg-white rounded-2xl shadow-card border border-ink-100 p-5 flex items-start justify-between animate-float-up">
      <div>
        <p className="text-sm text-ink-400 font-medium mb-1.5">{label}</p>
        <p className="font-mono text-3xl font-semibold text-ink-900 tabular-nums">{value}</p>
        {hint && <p className="text-xs text-ink-400 mt-1.5">{hint}</p>}
      </div>
      {Icon && (
        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${accentClasses}`}>
          <Icon className="w-5 h-5" aria-hidden="true" />
        </div>
      )}
    </div>
  )
}
