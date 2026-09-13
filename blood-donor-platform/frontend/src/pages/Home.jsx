import { Link } from 'react-router-dom'
import { Droplet, HeartPulse, MapPin, ShieldCheck, Users } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Button from '../components/common/Button.jsx'
import Card from '../components/common/Card.jsx'
import PulseLine from '../components/common/PulseLine.jsx'

const FEATURES = [
  {
    icon: ShieldCheck,
    title: 'Verified requests only',
    description:
      'Every blood request requires a hospital approval document before it goes live, so donors respond to real, verified need.',
  },
  {
    icon: MapPin,
    title: 'Find help nearby',
    description:
      'Donors see compatible requests sorted by distance, so the closest match can respond fastest when it matters.',
  },
  {
    icon: Users,
    title: 'Built for both sides',
    description:
      'One platform, two dashboards: recipients track every request they raise; donors track every life they help.',
  },
]

const STEPS = [
  { label: 'Register', text: 'Sign up as a donor or recipient and verify your email in minutes.' },
  { label: 'Connect', text: 'Recipients raise a verified request; nearby compatible donors are notified.' },
  { label: 'Respond', text: 'Donors volunteer with one tap; recipients see who is willing to help.' },
]

export default function Home() {
  return (
    <Layout>
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-b from-teal-50 to-white">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 pt-16 pb-20 sm:pt-24 sm:pb-28">
          <div className="max-w-2xl">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-teal-700 bg-teal-100 rounded-full px-3 py-1 mb-5">
              <Droplet className="w-3.5 h-3.5" /> A blood donor-recipient connection platform
            </span>
            <h1 className="text-4xl sm:text-5xl font-display font-bold text-ink-900 leading-tight mb-5">
              Every donor found in time is a life carried forward.
            </h1>
            <p className="text-lg text-ink-600 mb-8 max-w-xl">
              LifeLine matches verified blood requests with compatible donors nearby — so the
              right help arrives faster, with less back-and-forth.
            </p>
            <div className="flex flex-col sm:flex-row gap-3">
              <Link to="/register">
                <Button size="lg" fullWidth>
                  Register as a donor
                </Button>
              </Link>
              <Link to="/register">
                <Button size="lg" variant="outline" fullWidth>
                  Request blood
                </Button>
              </Link>
            </div>
          </div>
        </div>
        <PulseLine className="absolute bottom-0 left-0 w-full h-10 text-teal-300/70" strokeWidth={2} />
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-5 sm:px-8 py-20">
        <div className="text-center max-w-xl mx-auto mb-12">
          <h2 className="text-3xl font-display font-bold text-ink-900 mb-3">
            Built around one job: connecting people, safely
          </h2>
          <p className="text-ink-500">
            No noise, no unverified requests, no guesswork about who's compatible.
          </p>
        </div>
        <div className="grid sm:grid-cols-3 gap-6">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <Card key={title} hoverable>
              <div className="w-11 h-11 rounded-xl bg-teal-50 text-teal-600 flex items-center justify-center mb-4">
                <Icon className="w-5 h-5" />
              </div>
              <h3 className="text-lg font-semibold text-ink-900 mb-2">{title}</h3>
              <p className="text-sm text-ink-500 leading-relaxed">{description}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-ink-50 border-y border-ink-100">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-20">
          <div className="text-center max-w-xl mx-auto mb-12">
            <h2 className="text-3xl font-display font-bold text-ink-900 mb-3">How it works</h2>
          </div>
          <div className="grid sm:grid-cols-3 gap-8">
            {STEPS.map((step, idx) => (
              <div key={step.label} className="relative">
                <div className="flex items-center gap-3 mb-3">
                  <span className="w-9 h-9 rounded-full bg-teal-500 text-white font-mono font-semibold flex items-center justify-center text-sm">
                    {idx + 1}
                  </span>
                  <h3 className="font-semibold text-ink-900">{step.label}</h3>
                </div>
                <p className="text-sm text-ink-500 leading-relaxed pl-12">{step.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-5 sm:px-8 py-20 text-center">
        <HeartPulse className="w-10 h-10 text-crimson-500 mx-auto mb-5" />
        <h2 className="text-3xl font-display font-bold text-ink-900 mb-4">
          One registration away from being someone's match.
        </h2>
        <p className="text-ink-500 mb-8 max-w-md mx-auto">
          It takes a few minutes to sign up and verify your email. It could take a few minutes to
          save a life.
        </p>
        <Link to="/register">
          <Button size="lg">Get started</Button>
        </Link>
      </section>
    </Layout>
  )
}
