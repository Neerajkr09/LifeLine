import { useEffect, useState } from 'react'
import { CheckCircle2, Loader2, Mail, Phone, XCircle } from 'lucide-react'
import Modal from '../common/Modal.jsx'
import Button from '../common/Button.jsx'
import Alert from '../common/Alert.jsx'
import Card from '../common/Card.jsx'
import { acceptDonor, denyDonor, fetchWillingDonors } from '../../api/bloodRequestApi'
import { getApiErrorMessage } from '../../api/axiosInstance'

export default function WillingDonorsModal({ requestId, isOpen, onClose, onAccepted }) {
  const [donors, setDonors] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [actingDonorId, setActingDonorId] = useState(null)
  const [acceptedMessage, setAcceptedMessage] = useState('')

  const load = () => {
    if (!requestId) return
    setIsLoading(true)
    setError('')
    fetchWillingDonors(requestId)
      .then(setDonors)
      .catch((err) => setError(getApiErrorMessage(err)))
      .finally(() => setIsLoading(false))
  }

  useEffect(() => {
    if (!isOpen) return
    setAcceptedMessage('')
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, requestId])

  const handleAccept = async (donorId) => {
    setActingDonorId(donorId)
    setError('')
    try {
      const res = await acceptDonor(requestId, donorId)
      setAcceptedMessage(res.message)
      onAccepted?.(requestId)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setActingDonorId(null)
    }
  }

  const handleDeny = async (donorId) => {
    setActingDonorId(donorId)
    setError('')
    try {
      await denyDonor(requestId, donorId)
      setDonors((prev) => prev.filter((d) => d.donor_id !== donorId))
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setActingDonorId(null)
    }
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Willing donors">
      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-teal-500" />
        </div>
      ) : (
        <div className="space-y-4">
          {error && <Alert variant="error">{error}</Alert>}

          {acceptedMessage && (
            <Alert variant="success" title="Donor accepted">
              {acceptedMessage}
            </Alert>
          )}

          {!acceptedMessage && donors.length === 0 && (
            <p className="text-sm text-ink-500 text-center py-6">
              No one has volunteered for this request yet. Check back soon.
            </p>
          )}

          {!acceptedMessage &&
            donors.map((donor) => (
              <Card key={donor.donor_id} padded className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-crimson-600">{donor.blood_group}</span>
                  <span className="text-sm font-medium text-ink-900">
                    {donor.first_name} {donor.last_name}
                  </span>
                  <span className="text-xs text-ink-400">age {donor.age}</span>
                </div>
                <div className="space-y-1.5 text-sm text-ink-600">
                  <div className="flex items-center gap-2">
                    <Mail className="w-3.5 h-3.5 text-ink-400" /> {donor.email}
                  </div>
                  <div className="flex items-center gap-2">
                    <Phone className="w-3.5 h-3.5 text-ink-400" /> {donor.contact}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => handleAccept(donor.donor_id)}
                    isLoading={actingDonorId === donor.donor_id}
                  >
                    <CheckCircle2 className="w-4 h-4" /> Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDeny(donor.donor_id)}
                    disabled={actingDonorId === donor.donor_id}
                  >
                    <XCircle className="w-4 h-4" /> Deny
                  </Button>
                </div>
              </Card>
            ))}
        </div>
      )}
    </Modal>
  )
}
