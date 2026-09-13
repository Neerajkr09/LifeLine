import Layout from '../components/layout/Layout.jsx'
import RegistrationForm from '../components/auth/RegistrationForm.jsx'

export default function RegisterDonor() {
  return (
    <Layout>
      <section className="max-w-xl mx-auto px-5 py-12 sm:py-16">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-display font-bold text-ink-900">Register as a donor</h1>
          <p className="text-ink-500 text-sm mt-1.5">
            Join a network of donors ready to help when a compatible request comes in nearby.
          </p>
        </div>
        <RegistrationForm role="donor" />
      </section>
    </Layout>
  )
}
