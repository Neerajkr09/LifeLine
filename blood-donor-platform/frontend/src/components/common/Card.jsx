export default function Card({ children, className = '', padded = true, hoverable = false }) {
  return (
    <div
      className={`
        bg-white rounded-2xl shadow-card border border-ink-100
        ${padded ? 'p-6' : ''}
        ${hoverable ? 'transition-smooth hover:shadow-soft hover:-translate-y-0.5' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  )
}
