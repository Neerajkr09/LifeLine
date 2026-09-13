import { forwardRef } from 'react'

const Checkbox = forwardRef(function Checkbox({ label, error, className = '', ...rest }, ref) {
  return (
    <div>
      <label className="flex items-start gap-2.5 cursor-pointer select-none">
        <input
          ref={ref}
          type="checkbox"
          className={`mt-0.5 w-4.5 h-4.5 rounded border-ink-300 text-teal-500 focus:ring-teal-500 ${className}`}
          {...rest}
        />
        <span className="text-sm text-ink-700">{label}</span>
      </label>
      {error && <p className="mt-1 text-xs text-crimson-600">{error}</p>}
    </div>
  )
})

export default Checkbox
