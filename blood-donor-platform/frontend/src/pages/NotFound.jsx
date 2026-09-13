import { Link } from 'react-router-dom'
import { Droplet } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Button from '../components/common/Button.jsx'

export default function NotFound() {
  return (
    <Layout>
      <section className="max-w-md mx-auto px-5 py-24 text-center">
        <Droplet className="w-12 h-12 text-teal-300 mx-auto mb-5" />
        <h1 className="text-3xl font-display font-bold text-ink-900 mb-2">Page not found</h1>
        <p className="text-ink-500 mb-8">The page you're looking for doesn't exist or has moved.</p>
        <Link to="/">
          <Button>Back to home</Button>
        </Link>
      </section>
    </Layout>
  )
}
