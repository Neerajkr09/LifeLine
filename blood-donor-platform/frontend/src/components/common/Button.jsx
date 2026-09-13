import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'bg-teal-500 text-white hover:bg-teal-600 disabled:bg-teal-300',
  danger: 'bg-crimson-500 text-white hover:bg-crimson-600 disabled:bg-crimson-300',
  outline: 'bg-white text-teal-600 border border-teal-500 hover:bg-teal-50 disabled:text-teal-300 disabled:border-teal-200',
  ghost: 'bg-transparent text-ink-600 hover:bg-ink-100 disabled:text-ink-300',
}

const SIZES = {
  sm: 'text-sm px-3 py-1.5 rounded-lg',
  md: 'text-sm px-4 py-2.5 rounded-xl',
  lg: 'text-base px-6 py-3 rounded-xl',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  type = 'button',
  className = '',
  onClick,
  fullWidth = false,
  ...rest
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || isLoading}
      className={`
        inline-flex items-center justify-center gap-2 font-semibold
        transition-smooth disabled:cursor-not-allowed
        ${VARIANTS[variant]} ${SIZES[size]} ${fullWidth ? 'w-full' : ''} ${className}
      `}
      {...rest}
    >
      {isLoading && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  )
}
