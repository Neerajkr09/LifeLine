import { Link } from 'react-router-dom'
import { Droplet, HeartHandshake } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Card from '../components/common/Card.jsx'
import Button from '../components/common/Button.jsx'

export default function Register() {
  return (
    <Layout>
      <section className="max-w-3xl mx-auto px-5 py-16 sm:py-24 text-center">
        <h1 className="text-3xl font-display font-bold text-ink-900 mb-3">Join LifeLine</h1>
        <p className="text-ink-500 mb-12 max-w-lg mx-auto">
          Choose how you'd like to use the platform. You can always reach out the other way later
          from a separate account.
        </p>

        <div className="grid sm:grid-cols-2 gap-6 text-left">
          <Card hoverable className="flex flex-col">
            <div className="w-12 h-12 rounded-xl bg-crimson-50 text-crimson-600 flex items-center justify-center mb-4">
              <Droplet className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-semibold text-ink-900 mb-2">Register as Donor</h2>
            <p className="text-sm text-ink-500 mb-6 flex-1">
              Get notified of compatible blood requests nearby and volunteer to help when you can.
            </p>
            <Link to="/register/donor">
              <Button fullWidth>Continue as donor</Button>
            </Link>
          </Card>

          <Card hoverable className="flex flex-col">
            <div className="w-12 h-12 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mb-4">
              <HeartHandshake className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-semibold text-ink-900 mb-2">Register as Recipient</h2>
            <p className="text-sm text-ink-500 mb-6 flex-1">
              Raise a verified blood request for yourself or someone else, and track willing
              donors as they respond.
            </p>
            <Link to="/register/recipient">
              <Button fullWidth variant="outline">
                Continue as recipient
              </Button>
            </Link>
          </Card>
        </div>
      </section>
    </Layout>
  )
}
