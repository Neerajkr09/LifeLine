import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, MapPin, UploadCloud, User, Users } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Card from '../components/common/Card.jsx'
import Input from '../components/common/Input.jsx'
import Select from '../components/common/Select.jsx'
import Checkbox from '../components/common/Checkbox.jsx'
import Button from '../components/common/Button.jsx'
import Alert from '../components/common/Alert.jsx'
import Modal from '../components/common/Modal.jsx'
import OtpVerification from '../components/auth/OtpVerification.jsx'
import { useAuth } from '../hooks/useAuth'
import { useGeolocation } from '../hooks/useGeolocation'
import { bloodRequestOtherSchema } from '../utils/validationSchemas'
import { BLOOD_GROUP_OPTIONS } from '../utils/bloodGroups'
import { createBloodRequest } from '../api/bloodRequestApi'
import { getApiErrorMessage } from '../api/axiosInstance'

const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
const MAX_FILE_MB = 5

export default function BloodRequestForm() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const { coordinates, requestLocation } = useGeolocation()
  const fileInputRef = useRef(null)

  const [requestFor, setRequestFor] = useState(null) // 'self' | 'other'
  const [otherEmailVerified, setOtherEmailVerified] = useState(false)
  const [file, setFile] = useState(null)
  const [fileError, setFileError] = useState('')
  const [locationError, setLocationError] = useState('')
  const [isWarningOpen, setIsWarningOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [apiError, setApiError] = useState('')

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid: isOtherFormValid },
  } = useForm({ resolver: yupResolver(bloodRequestOtherSchema), mode: 'onChange' })

  const otherEmail = watch('email')

  const handleSelectFor = (value) => {
    setRequestFor(value)
    setApiError('')
  }

  const handleLocationRequest = async () => {
    setLocationError('')
    try {
      await requestLocation()
    } catch {
      setLocationError('We could not access your location. Location access is required to submit a request.')
    }
  }

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0]
    setFileError('')
    if (!selected) {
      setFile(null)
      return
    }
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setFileError('Please upload a PDF or image file (PDF, JPG, or PNG).')
      setFile(null)
      return
    }
    if (selected.size > MAX_FILE_MB * 1024 * 1024) {
      setFileError(`File is too large. Maximum size is ${MAX_FILE_MB}MB.`)
      setFile(null)
      return
    }
    setFile(selected)
  }

  const canOpenWarning =
    requestFor && !!coordinates && !!file && (requestFor === 'self' || (isOtherFormValid && otherEmailVerified))

  const doSubmit = async (otherValues) => {
    setApiError('')
    setIsSubmitting(true)
    try {
      const baseFields = {
        for_self: requestFor === 'self' ? 'true' : 'false',
        for_other: requestFor === 'other' ? 'true' : 'false',
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
        accepted_warning: 'true',
      }
      const fields =
        requestFor === 'self'
          ? baseFields
          : {
              ...baseFields,
              first_name: otherValues.first_name,
              last_name: otherValues.last_name,
              age: otherValues.age,
              blood_group: otherValues.blood_group,
              contact: otherValues.contact,
              email: otherValues.email,
              address_line: otherValues.address_line,
              postcode: otherValues.postcode,
              city_town: otherValues.city_town,
            }
      await createBloodRequest(fields, file)
      navigate('/recipient/dashboard', { replace: true })
    } catch (err) {
      setApiError(getApiErrorMessage(err))
      setIsWarningOpen(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleConfirmSubmit = async () => {
    if (requestFor === 'self') {
      await doSubmit({})
    } else {
      await handleSubmit(doSubmit)()
    }
  }

  return (
    <Layout>
      <section className="max-w-2xl mx-auto px-5 py-10 sm:py-14">
        <div className="mb-8">
          <h1 className="text-2xl font-display font-bold text-ink-900">Blood Type Request</h1>
          <p className="text-ink-500 text-sm mt-1.5">
            Requests are reviewed against your hospital approval document and can't be edited once submitted.
          </p>
        </div>

        {apiError && (
          <Alert variant="error" className="mb-6">
            {apiError}
          </Alert>
        )}

        <Card className="space-y-6">
          <div>
            <p className="text-sm font-semibold text-ink-900 mb-3">Who is this request for?</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => handleSelectFor('self')}
                className={`flex items-center gap-3 p-4 rounded-xl border-2 text-left transition-smooth ${
                  requestFor === 'self' ? 'border-teal-500 bg-teal-50' : 'border-ink-200 hover:border-teal-300'
                }`}
              >
                <User className="w-5 h-5 text-teal-600 shrink-0" />
                <div>
                  <p className="font-medium text-ink-900 text-sm">Myself</p>
                  <p className="text-xs text-ink-500">We'll use your profile details</p>
                </div>
              </button>
              <button
                type="button"
                onClick={() => handleSelectFor('other')}
                className={`flex items-center gap-3 p-4 rounded-xl border-2 text-left transition-smooth ${
                  requestFor === 'other' ? 'border-teal-500 bg-teal-50' : 'border-ink-200 hover:border-teal-300'
                }`}
              >
                <Users className="w-5 h-5 text-teal-600 shrink-0" />
                <div>
                  <p className="font-medium text-ink-900 text-sm">Someone else</p>
                  <p className="text-xs text-ink-500">Enter the patient's details</p>
                </div>
              </button>
            </div>
          </div>

          {requestFor === 'self' && user && (
            <div className="border-t border-ink-100 pt-5">
              <p className="text-sm font-semibold text-ink-900 mb-3">Your details (from your profile)</p>
              <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div>
                  <dt className="text-ink-400">Name</dt>
                  <dd className="text-ink-800">
                    {user.first_name} {user.last_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-ink-400">Blood group</dt>
                  <dd className="text-ink-800 font-mono">{user.blood_group}</dd>
                </div>
                <div>
                  <dt className="text-ink-400">Contact</dt>
                  <dd className="text-ink-800">{user.contact}</dd>
                </div>
                <div>
                  <dt className="text-ink-400">Email</dt>
                  <dd className="text-ink-800">{user.email}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-ink-400">Address</dt>
                  <dd className="text-ink-800">
                    {user.address.address_line}, {user.address.city_town} {user.address.postcode}
                  </dd>
                </div>
              </dl>
            </div>
          )}

          {requestFor === 'other' && (
            <div className="border-t border-ink-100 pt-5 space-y-4">
              <p className="text-sm font-semibold text-ink-900">Patient details</p>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input id="first_name" label="First name" required error={errors.first_name?.message} {...register('first_name')} />
                <Input id="last_name" label="Last name" required error={errors.last_name?.message} {...register('last_name')} />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input id="age" label="Age" type="number" required error={errors.age?.message} {...register('age')} />
                <Select
                  id="blood_group"
                  label="Blood group"
                  required
                  options={BLOOD_GROUP_OPTIONS}
                  error={errors.blood_group?.message}
                  {...register('blood_group')}
                />
              </div>
              <div className="grid sm:grid-cols-2 gap-4">
                <Input id="contact" label="Contact number" required error={errors.contact?.message} {...register('contact')} />
                <Input id="email" label="Email" type="email" required error={errors.email?.message} {...register('email')} />
              </div>
              <Input id="address_line" label="Address line" required error={errors.address_line?.message} {...register('address_line')} />
              <div className="grid sm:grid-cols-2 gap-4">
                <Input id="postcode" label="Postcode" required error={errors.postcode?.message} {...register('postcode')} />
                <Input id="city_town" label="City / Town" required error={errors.city_town?.message} {...register('city_town')} />
              </div>

              <div>
                <p className="text-sm font-medium text-ink-800 mb-1.5">
                  Verify the patient's email <span className="text-crimson-500">*</span>
                </p>
                <OtpVerification
                  email={otherEmail}
                  purpose="blood_request"
                  verified={otherEmailVerified}
                  onVerified={() => setOtherEmailVerified(true)}
                  disabled={!!errors.email || !otherEmail}
                />
              </div>
            </div>
          )}

          {requestFor && (
            <>
              <div className="border-t border-ink-100 pt-5">
                <Checkbox
                  label="I grant location access so my precise location is attached to this request (mandatory)."
                  checked={!!coordinates}
                  onChange={(e) => {
                    if (e.target.checked) handleLocationRequest()
                  }}
                />
                {coordinates && (
                  <p className="flex items-center gap-1.5 text-xs text-teal-700 mt-2">
                    <MapPin className="w-3.5 h-3.5" /> Location captured.
                  </p>
                )}
                {locationError && (
                  <Alert variant="error" className="mt-3">
                    {locationError}
                  </Alert>
                )}
              </div>

              <div className="border-t border-ink-100 pt-5">
                <p className="text-sm font-semibold text-ink-900 mb-1">
                  Hospital approval form <span className="text-crimson-500">*</span>
                </p>
                <p className="text-xs text-ink-500 mb-3">Upload as PDF, JPG, or PNG (max {MAX_FILE_MB}MB).</p>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full flex items-center gap-3 p-4 rounded-xl border-2 border-dashed border-ink-200 hover:border-teal-400 transition-smooth text-left"
                >
                  <UploadCloud className="w-5 h-5 text-teal-600 shrink-0" />
                  <span className="text-sm text-ink-600 truncate">
                    {file ? file.name : 'Click to choose a file'}
                  </span>
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={handleFileChange}
                />
                {fileError && <p className="text-xs text-crimson-600 mt-1.5">{fileError}</p>}
              </div>

              <Button
                fullWidth
                size="lg"
                disabled={!canOpenWarning}
                onClick={() => setIsWarningOpen(true)}
              >
                Review and submit request
              </Button>
            </>
          )}
        </Card>
      </section>

      <Modal
        isOpen={isWarningOpen}
        onClose={() => setIsWarningOpen(false)}
        title="Beware!!"
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsWarningOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" isLoading={isSubmitting} onClick={handleConfirmSubmit}>
              I understand, submit request
            </Button>
          </>
        }
      >
        <div className="flex gap-3">
          <AlertTriangle className="w-8 h-8 text-crimson-500 shrink-0" />
          <p className="text-sm text-ink-600">
            Once a request is submitted, it can never be edited. Uploading a fake hospital approval
            document for a blood requirement will result in a <strong>permanent account ban</strong>.
            Please confirm every detail is accurate before continuing.
          </p>
        </div>
      </Modal>
    </Layout>
  )
}
