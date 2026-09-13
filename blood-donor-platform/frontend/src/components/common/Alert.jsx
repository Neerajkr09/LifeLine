import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'

const VARIANTS = {
  success: { wrap: 'bg-teal-50 border-teal-200 text-teal-800', Icon: CheckCircle2, iconColor: 'text-teal-600' },
  error: { wrap: 'bg-crimson-50 border-crimson-200 text-crimson-800', Icon: XCircle, iconColor: 'text-crimson-600' },
  warning: { wrap: 'bg-amber-50 border-amber-200 text-amber-800', Icon: AlertTriangle, iconColor: 'text-amber-600' },
  info: { wrap: 'bg-ink-100 border-ink-200 text-ink-700', Icon: Info, iconColor: 'text-ink-500' },
}

export default function Alert({ variant = 'info', title, children, className = '' }) {
  const { wrap, Icon, iconColor } = VARIANTS[variant]
  return (
    <div className={`flex gap-3 items-start border rounded-xl p-4 ${wrap} ${className}`} role="alert">
      <Icon className={`w-5 h-5 shrink-0 mt-0.5 ${iconColor}`} aria-hidden="true" />
      <div className="text-sm">
        {title && <p className="font-semibold mb-0.5">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}
