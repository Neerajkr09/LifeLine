import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Droplet, FileText, HeartHandshake, ListChecks, Plus, Users } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Card from '../components/common/Card.jsx'
import StatCard from '../components/common/StatCard.jsx'
import Button from '../components/common/Button.jsx'
import Spinner from '../components/common/Spinner.jsx'
import Alert from '../components/common/Alert.jsx'
import WillingDonorsModal from '../components/recipient/WillingDonorsModal.jsx'
import { useAuth } from '../hooks/useAuth'
import { fetchRecipientDashboard } from '../api/dashboardApi'
import { downloadHospitalDocument, fetchMyRequests } from '../api/bloodRequestApi'
import { getApiErrorMessage } from '../api/axiosInstance'

const STATUS_STYLES = {
  active: 'bg-teal-50 text-teal-700 border-teal-200',
  fulfilled: 'bg-ink-100 text-ink-600 border-ink-200',
  cancelled: 'bg-crimson-50 text-crimson-700 border-crimson-200',
}

function StatusBadge({ status }) {
  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full border capitalize ${STATUS_STYLES[status] || ''}`}>
      {status}
    </span>
  )
}

export default function RecipientDashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [requests, setRequests] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [reviewRequestId, setReviewRequestId] = useState(null)

  const loadData = () => {
    setIsLoading(true)
    return Promise.all([fetchRecipientDashboard(), fetchMyRequests()])
      .then(([statsData, requestsData]) => {
        setStats(statsData)
        setRequests(requestsData)
      })
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleDownload = async (requestId) => {
    try {
      await downloadHospitalDocument(requestId, `hospital-approval-${requestId}`)
    } catch (err) {
      setError(getApiErrorMessage(err))
    }
  }

  const handleDonorAccepted = () => {
    // The accepted request is now "fulfilled" and its willing-donor list is
    // moot -- reload everything so stats and statuses reflect that.
    loadData()
  }

  return (
    <Layout>
      <section className="max-w-6xl mx-auto px-5 sm:px-8 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-display font-bold text-ink-900">
            Welcome back, {user?.first_name}
          </h1>
          <p className="text-ink-500 text-sm mt-1">Here's where things stand with your requests.</p>
        </div>

        {error && (
          <Alert variant="error" className="mb-6">
            {error}
          </Alert>
        )}

        {isLoading ? (
          <Spinner fullPage label="Loading your dashboard..." />
        ) : (
          <>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-10">
              <StatCard label="Requests raised" value={stats.requests_raised} icon={ListChecks} accent="ink" />
              <StatCard label="Active requests" value={stats.active_requests} icon={Droplet} accent="teal" />
              <StatCard
                label="Successful requests"
                value={stats.successful_requests}
                icon={HeartHandshake}
                accent="teal"
              />
              <StatCard label="Willing donors" value={stats.willing_donor_count} icon={Users} accent="crimson" />
            </div>

            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold text-ink-900">Your requests</h2>
              <Link to="/blood-request/new">
                <Button size="sm">
                  <Plus className="w-4 h-4" /> Create request
                </Button>
              </Link>
            </div>

            {requests.length === 0 ? (
              <Card className="text-center py-12">
                <Droplet className="w-10 h-10 text-teal-300 mx-auto mb-3" />
                <p className="text-ink-500 mb-5">You haven't raised any requests yet.</p>
                <Link to="/blood-request/new">
                  <Button>Create your first request</Button>
                </Link>
              </Card>
            ) : (
              <div className="space-y-4">
                {requests.map((req) => (
                  <Card key={req.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2.5 mb-1.5">
                        <span className="font-mono font-semibold text-ink-900">
                          {req.patient.blood_group}
                        </span>
                        <StatusBadge status={req.status} />
                        {req.for_self && (
                          <span className="text-xs text-ink-400 border border-ink-200 rounded-full px-2 py-0.5">
                            For self
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-ink-600">
                        {req.patient.first_name} {req.patient.last_name} &middot;{' '}
                        {req.patient.address.city_town}
                      </p>
                      <p className="text-xs text-ink-400 mt-1">
                        Raised {new Date(req.created_at).toLocaleDateString()} &middot;{' '}
                        {req.willing_donor_count} willing donor{req.willing_donor_count === 1 ? '' : 's'}
                      </p>
                    </div>
                    <div className="flex gap-2.5 shrink-0">
                      {req.status === 'active' && req.willing_donor_count > 0 && (
                        <Button size="sm" onClick={() => setReviewRequestId(req.id)}>
                          <Users className="w-4 h-4" /> Review donors
                        </Button>
                      )}
                      <Button variant="outline" size="sm" onClick={() => handleDownload(req.id)}>
                        <FileText className="w-4 h-4" /> Hospital document
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <WillingDonorsModal
        requestId={reviewRequestId}
        isOpen={!!reviewRequestId}
        onClose={() => setReviewRequestId(null)}
        onAccepted={handleDonorAccepted}
      />
    </Layout>
  )
}
