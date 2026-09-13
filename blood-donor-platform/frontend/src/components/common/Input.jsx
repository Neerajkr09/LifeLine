import { forwardRef } from 'react'

const Input = forwardRef(function Input(
  { label, error, hint, required, className = '', containerClassName = '', ...rest },
  ref,
) {
  return (
    <div className={containerClassName}>
      {label && (
        <label htmlFor={rest.id} className="block text-sm font-medium text-ink-800 mb-1.5">
          {label}
          {required && <span className="text-crimson-500 ml-0.5">*</span>}
        </label>
      )}
      <input
        ref={ref}
        className={`
          w-full px-3.5 py-2.5 rounded-xl border bg-white text-ink-800 placeholder:text-ink-400
          transition-smooth
          ${error ? 'border-crimson-400 focus:border-crimson-500' : 'border-ink-200 focus:border-teal-500'}
          ${className}
        `}
        aria-invalid={!!error}
        {...rest}
      />
      {hint && !error && <p className="mt-1 text-xs text-ink-400">{hint}</p>}
      {error && <p className="mt-1 text-xs text-crimson-600">{error}</p>}
    </div>
  )
})

export default Input
