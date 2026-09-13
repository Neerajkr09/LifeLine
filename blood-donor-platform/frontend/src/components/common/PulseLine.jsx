/**
 * The platform's signature element: an ECG/heartbeat pulse line. Ties
 * together "blood" and "life" thematically without leaning on stock-photo
 * imagery. Reused at different scales across the navbar mark, hero section,
 * and section dividers so it reads as one consistent identity.
 */
export default function PulseLine({ className = '', animated = true, strokeWidth = 3 }) {
  return (
    <svg
      viewBox="0 0 400 60"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path
        d="M0 30 H120 L140 10 L160 50 L180 6 L200 54 L220 30 H400"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={animated ? 1000 : undefined}
        strokeDasharray={animated ? 1000 : undefined}
        className={animated ? 'animate-pulse-line' : ''}
      />
    </svg>
  )
}
