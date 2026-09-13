import { Loader2 } from 'lucide-react'

export default function Spinner({ size = 'md', label = 'Loading...', fullPage = false }) {
  const sizeClass = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }[size]

  const spinner = (
    <div className="flex flex-col items-center gap-3 text-ink-500">
      <Loader2 className={`${sizeClass} animate-spin text-teal-500`} aria-hidden="true" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  )

  if (fullPage) {
    return <div className="min-h-[60vh] flex items-center justify-center">{spinner}</div>
  }
  return spinner
}
