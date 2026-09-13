import { useEffect, useState } from 'react'
import { Droplet, HeartHandshake, Info, MapPin, Users } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Card from '../components/common/Card.jsx'
import StatCard from '../components/common/StatCard.jsx'
import Spinner from '../components/common/Spinner.jsx'
import Alert from '../components/common/Alert.jsx'
import DonorRequestDetailModal from '../components/donor/DonorRequestDetailModal.jsx'
import { useAuth } from '../hooks/useAuth'
import { fetchDonorDashboard } from '../api/dashboardApi'
import { fetchMatchingRequests } from '../api/bloodRequestApi'
import { getApiErrorMessage } from '../api/axiosInstance'

export default function DonorDashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [requests, setRequests] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [resolvedIds, setResolvedIds] = useState({}) // requestId -> 'willing' | 'rejected'
  const [openRequestId, setOpenRequestId] = useState(null)

  const loadData = () => {
    setIsLoading(true)
    Promise.all([fetchDonorDashboard(), fetchMatchingRequests()])
      .then(([statsData, requestsData]) => {
        setStats(statsData)
        setRequests(requestsData)
      })
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleResolved = (outcome, requestId) => {
    setResolvedIds((prev) => ({ ...prev, [requestId]: outcome }))
    // Refresh stats in the background so "times volunteered" etc. stay current
    // without a jarring full-page reload.
    fetchDonorDashboard().then(setStats).catch(() => {})
  }

  return (
    <Layout>
      <section className="max-w-6xl mx-auto px-5 sm:px-8 py-10">
        <div className="mb-6">
          <h1 className="text-2xl font-display font-bold text-ink-900">
            Welcome back, {user?.first_name}
          </h1>
          <p className="text-ink-500 text-sm mt-1">
            Thank you for being a donor -- here's what's happening nearby.
          </p>
        </div>

        <Alert variant="info" className="mb-8">
          <div className="flex gap-2 items-start">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <p>
              Please provide willingness for multiple requests to gain maximum reach! Be relaxed --
              only one accepted request from the recipient's side will be finalised, so you'll only
              ever end up donating to one person. Please donate at the clinic mentioned in the
              document uploaded by the blood seeker, and only the quantity mentioned there.
            </p>
          </div>
        </Alert>

        {error && (
          <Alert variant="error" className="mb-6">
            {error}
          </Alert>
        )}

        {isLoading ? (
          <Spinner fullPage label="Loading your dashboard..." />
        ) : (
          <>
            <div className="grid sm:grid-cols-3 gap-5 mb-10">
              <StatCard
                label="Matching requests nearby"
                value={stats.matching_requests_nearby}
                icon={Droplet}
                accent="crimson"
              />
              <StatCard label="Times volunteered" value={stats.times_volunteered} icon={HeartHandshake} accent="teal" />
              <StatCard label="Confirmed donations" value={stats.confirmed_donations} icon={Users} accent="ink" />
            </div>

            <h2 className="text-lg font-semibold text-ink-900 mb-1.5">Requests you can help with</h2>
            <p className="text-sm text-ink-500 mb-5">
              Matched to your blood group and within 5km of your location. Tap a request to see full
              details and the hospital approval document before deciding.
            </p>

            {requests.length === 0 ? (
              <Card className="text-center py-12">
                <Droplet className="w-10 h-10 text-teal-300 mx-auto mb-3" />
                <p className="text-ink-500">
                  No matching requests right now. We'll show compatible requests here as they come in.
                </p>
              </Card>
            ) : (
              <div className="space-y-4">
                {requests.map((req) => {
                  const outcome = resolvedIds[req.id]
                  return (
                    <button
                      key={req.id}
                      type="button"
                      onClick={() => setOpenRequestId(req.id)}
                      className="w-full text-left"
                    >
                      <Card
                        hoverable
                        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
                      >
                        <div>
                          <div className="flex items-center gap-2.5 mb-1.5">
                            <span className="font-mono font-semibold text-lg text-crimson-600">
                              {req.blood_group}
                            </span>
                            <span className="text-sm text-ink-800 font-medium">
                              {req.first_name} {req.last_name}, {req.age}
                            </span>
                            {outcome && (
                              <span
                                className={`text-xs rounded-full px-2 py-0.5 ${
                                  outcome === 'willing'
                                    ? 'bg-teal-50 text-teal-700 border border-teal-200'
                                    : 'bg-ink-100 text-ink-500 border border-ink-200'
                                }`}
                              >
                                {outcome === 'willing' ? "You're willing" : 'You rejected'}
                              </span>
                            )}
                          </div>
                          <p className="flex items-center gap-1.5 text-sm text-ink-600">
                            <MapPin className="w-3.5 h-3.5 text-ink-400" />
                            {req.city_town}
                            {req.distance_km != null && ` · ${req.distance_km} km away`}
                          </p>
                          <p className="text-xs text-ink-400 mt-1">
                            Raised {new Date(req.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <span className="text-sm font-medium text-teal-600 shrink-0">View details →</span>
                      </Card>
                    </button>
                  )
                })}
              </div>
            )}
          </>
        )}
      </section>

      <DonorRequestDetailModal
        requestId={openRequestId}
        isOpen={!!openRequestId}
        onClose={() => setOpenRequestId(null)}
        onResolved={handleResolved}
      />
    </Layout>
  )
}
