import { forwardRef } from 'react'
import { ChevronDown } from 'lucide-react'

const Select = forwardRef(function Select(
  { label, error, required, options, placeholder = 'Select...', className = '', containerClassName = '', ...rest },
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
      <div className="relative">
        <select
          ref={ref}
          className={`
            w-full appearance-none px-3.5 py-2.5 rounded-xl border bg-white text-ink-800
            transition-smooth pr-10
            ${error ? 'border-crimson-400 focus:border-crimson-500' : 'border-ink-200 focus:border-teal-500'}
            ${className}
          `}
          aria-invalid={!!error}
          {...rest}
        >
          <option value="">{placeholder}</option>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="w-4 h-4 text-ink-400 absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
      </div>
      {error && <p className="mt-1 text-xs text-crimson-600">{error}</p>}
    </div>
  )
})

export default Select
