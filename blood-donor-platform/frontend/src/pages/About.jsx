import { Link } from 'react-router-dom'
import { CheckCircle2 } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Button from '../components/common/Button.jsx'
import Card from '../components/common/Card.jsx'

const COMMITMENTS = [
  'Every request requires a hospital approval document before donors ever see it.',
  'Location is only ever used to sort by distance — never shared publicly.',
  'Submitted requests can\'t be edited afterward, protecting the integrity of every case.',
  'Uploading a fake hospital approval results in a permanent account ban.',
]

export default function About() {
  return (
    <Layout>
      <section className="max-w-4xl mx-auto px-5 sm:px-8 py-16 sm:py-20">
        <h1 className="text-4xl font-display font-bold text-ink-900 mb-5">About LifeLine</h1>
        <p className="text-lg text-ink-600 leading-relaxed mb-6">
          LifeLine exists to close the gap between people who need blood and people who are
          willing to give it. Instead of relying on chain messages and last-minute phone calls,
          recipients raise a verified request and nearby, blood-type-compatible donors are shown
          exactly who needs help and how far away they are.
        </p>
        <p className="text-lg text-ink-600 leading-relaxed mb-10">
          We built the platform around trust: every request carries a hospital approval document,
          every account is email-verified, and every submitted request is locked in place so it
          can't be altered after the fact.
        </p>

        <Card className="mb-10">
          <h2 className="text-xl font-semibold text-ink-900 mb-4">Our commitments</h2>
          <ul className="space-y-3">
            {COMMITMENTS.map((item) => (
              <li key={item} className="flex gap-3 text-sm text-ink-600">
                <CheckCircle2 className="w-5 h-5 text-teal-500 shrink-0 mt-0.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </Card>

        <div className="text-center">
          <Link to="/register">
            <Button size="lg">Join LifeLine</Button>
          </Link>
        </div>
      </section>
    </Layout>
  )
}
