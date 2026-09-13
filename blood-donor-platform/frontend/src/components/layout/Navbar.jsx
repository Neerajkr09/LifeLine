import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { Droplet, LayoutDashboard, LogOut, Menu, X } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import Button from '../common/Button'

export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuth()
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const navigate = useNavigate()

  const dashboardPath = user?.role === 'donor' ? '/donor/dashboard' : '/recipient/dashboard'

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const navLinkClass = ({ isActive }) =>
    `text-sm font-medium transition-smooth ${isActive ? 'text-teal-600' : 'text-ink-600 hover:text-teal-600'}`

  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-ink-100">
      <nav className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 shrink-0" onClick={() => setIsMenuOpen(false)}>
          <span className="w-9 h-9 rounded-xl bg-teal-500 flex items-center justify-center">
            <Droplet className="w-5 h-5 text-white" fill="white" fillOpacity={0.25} />
          </span>
          <span className="font-display font-bold text-lg text-ink-900">LifeLine</span>
        </Link>

        <div className="hidden md:flex items-center gap-8">
          <NavLink to="/" end className={navLinkClass}>
            Home
          </NavLink>
          <NavLink to="/about" className={navLinkClass}>
            About
          </NavLink>
        </div>

        <div className="hidden md:flex items-center gap-3">
          {isAuthenticated ? (
            <>
              <Link to={dashboardPath}>
                <Button variant="ghost" size="sm">
                  <LayoutDashboard className="w-4 h-4" /> Dashboard
                </Button>
              </Link>
              <Button variant="outline" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4" /> Log out
              </Button>
            </>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost" size="sm">
                  Log in
                </Button>
              </Link>
              <Link to="/register">
                <Button variant="primary" size="sm">
                  Register
                </Button>
              </Link>
            </>
          )}
        </div>

        <button
          className="md:hidden p-2 text-ink-700"
          onClick={() => setIsMenuOpen((open) => !open)}
          aria-label={isMenuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={isMenuOpen}
        >
          {isMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </nav>

      {isMenuOpen && (
        <div className="md:hidden border-t border-ink-100 bg-white px-5 py-4 flex flex-col gap-4">
          <NavLink to="/" end className={navLinkClass} onClick={() => setIsMenuOpen(false)}>
            Home
          </NavLink>
          <NavLink to="/about" className={navLinkClass} onClick={() => setIsMenuOpen(false)}>
            About
          </NavLink>
          <div className="h-px bg-ink-100" />
          {isAuthenticated ? (
            <>
              <Link to={dashboardPath} onClick={() => setIsMenuOpen(false)}>
                <Button variant="outline" size="sm" fullWidth>
                  <LayoutDashboard className="w-4 h-4" /> Dashboard
                </Button>
              </Link>
              <Button variant="ghost" size="sm" fullWidth onClick={handleLogout}>
                <LogOut className="w-4 h-4" /> Log out
              </Button>
            </>
          ) : (
            <>
              <Link to="/login" onClick={() => setIsMenuOpen(false)}>
                <Button variant="ghost" size="sm" fullWidth>
                  Log in
                </Button>
              </Link>
              <Link to="/register" onClick={() => setIsMenuOpen(false)}>
                <Button variant="primary" size="sm" fullWidth>
                  Register
                </Button>
              </Link>
            </>
          )}
        </div>
      )}
    </header>
  )
}
