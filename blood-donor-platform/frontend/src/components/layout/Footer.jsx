import { Link } from 'react-router-dom'
import { Droplet } from 'lucide-react'

export default function Footer() {
  return (
    <footer className="bg-ink-900 text-ink-100 mt-24">
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12 grid gap-10 sm:grid-cols-3">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-8 h-8 rounded-lg bg-teal-500 flex items-center justify-center">
              <Droplet className="w-4 h-4 text-white" fill="white" fillOpacity={0.25} />
            </span>
            <span className="font-display font-bold text-lg text-white">LifeLine</span>
          </div>
          <p className="text-sm text-ink-400 max-w-xs">
            Connecting verified blood donors with people who need them, quickly and safely.
          </p>
        </div>
        <div>
          <p className="text-sm font-semibold text-white mb-3">Platform</p>
          <ul className="space-y-2 text-sm text-ink-400">
            <li>
              <Link to="/about" className="hover:text-teal-400 transition-smooth">
                About
              </Link>
            </li>
            <li>
              <Link to="/register" className="hover:text-teal-400 transition-smooth">
                Become a donor
              </Link>
            </li>
            <li>
              <Link to="/login" className="hover:text-teal-400 transition-smooth">
                Request blood
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold text-white mb-3">Need urgent help?</p>
          <p className="text-sm text-ink-400">
            LifeLine connects donors and recipients but does not replace emergency medical care.
            In a medical emergency, contact your local emergency services immediately.
          </p>
        </div>
      </div>
      <div className="border-t border-ink-800 py-5 text-center text-xs text-ink-500">
        © {new Date().getFullYear()} LifeLine Blood Donor-Recipient Connection Platform.
      </div>
    </footer>
  )
}
