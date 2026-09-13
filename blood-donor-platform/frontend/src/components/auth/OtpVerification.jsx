import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Loader2, MailCheck } from 'lucide-react'
import { sendOtp, verifyOtp } from '../../api/authApi'
import { getApiErrorMessage } from '../../api/axiosInstance'
import Button from '../common/Button.jsx'
import Input from '../common/Input.jsx'
import Alert from '../common/Alert.jsx'

const RESEND_COOLDOWN_SECONDS = 30
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function OtpVerification({ email, purpose = 'registration', verified, onVerified, disabled }) {
  const [otp, setOtp] = useState('')
  const [otpSent, setOtpSent] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [isVerifying, setIsVerifying] = useState(false)
  const [error, setError] = useState('')
  const [infoMessage, setInfoMessage] = useState('')
  const [cooldown, setCooldown] = useState(0)
  const sentForEmail = useRef('')

  useEffect(() => {
    // If the person edits the email after verifying/sending, the previous
    // code no longer applies -- reset so they must verify the new address.
    if (sentForEmail.current && sentForEmail.current !== email) {
      setOtpSent(false)
      setOtp('')
      setInfoMessage('')
    }
  }, [email])

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  const isEmailValid = EMAIL_PATTERN.test(email || '')

  const handleSendOtp = async () => {
    setError('')
    setInfoMessage('')
    setIsSending(true)
    try {
      await sendOtp(email, purpose)
      sentForEmail.current = email
      setOtpSent(true)
      setCooldown(RESEND_COOLDOWN_SECONDS)
      setInfoMessage(`We sent a verification code to ${email}.`)
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setIsSending(false)
    }
  }

  const handleVerifyOtp = async () => {
    setError('')
    setIsVerifying(true)
    try {
      await verifyOtp(email, otp, purpose)
      onVerified(email)
      setInfoMessage('')
    } catch (err) {
      setError(getApiErrorMessage(err))
    } finally {
      setIsVerifying(false)
    }
  }

  if (verified) {
    return (
      <div className="flex items-center gap-2 text-teal-700 bg-teal-50 border border-teal-200 rounded-xl px-3.5 py-2.5 text-sm font-medium">
        <CheckCircle2 className="w-4 h-4" />
        Email Verified
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {!otpSent ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleSendOtp}
          isLoading={isSending}
          disabled={disabled || !isEmailValid}
        >
          <MailCheck className="w-4 h-4" /> Send verification code
        </Button>
      ) : (
        <div className="flex flex-col sm:flex-row gap-2.5 items-start sm:items-end">
          <Input
            id="otp-input"
            label="Enter the 6-digit code"
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="000000"
            inputMode="numeric"
            containerClassName="w-40"
          />
          <Button
            type="button"
            variant="primary"
            size="md"
            onClick={handleVerifyOtp}
            isLoading={isVerifying}
            disabled={otp.length < 4}
          >
            Verify
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="md"
            onClick={handleSendOtp}
            disabled={cooldown > 0 || isSending}
          >
            {isSending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : cooldown > 0 ? (
              `Resend in ${cooldown}s`
            ) : (
              'Resend code'
            )}
          </Button>
        </div>
      )}
      {infoMessage && <Alert variant="info">{infoMessage}</Alert>}
      {error && <Alert variant="error">{error}</Alert>}
    </div>
  )
}
