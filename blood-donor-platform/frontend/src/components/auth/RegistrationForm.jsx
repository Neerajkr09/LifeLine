import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import { useNavigate } from 'react-router-dom'
import { MapPin } from 'lucide-react'
import Card from '../common/Card.jsx'
import Input from '../common/Input.jsx'
import Select from '../common/Select.jsx'
import Checkbox from '../common/Checkbox.jsx'
import Button from '../common/Button.jsx'
import Alert from '../common/Alert.jsx'
import OtpVerification from './OtpVerification.jsx'
import { useAuth } from '../../hooks/useAuth'
import { useGeolocation } from '../../hooks/useGeolocation'
import { registerSchema } from '../../utils/validationSchemas'
import { BLOOD_GROUP_OPTIONS } from '../../utils/bloodGroups'
import { getApiErrorMessage } from '../../api/axiosInstance'

export default function RegistrationForm({ role }) {
  const { register: registerUser } = useAuth()
  const navigate = useNavigate()
  const { coordinates, requestLocation } = useGeolocation()
  const [emailVerified, setEmailVerified] = useState(false)
  const [locationError, setLocationError] = useState('')
  const [apiError, setApiError] = useState('')

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors, isSubmitting, isValid },
  } = useForm({
    resolver: yupResolver(registerSchema),
    mode: 'onChange',
    defaultValues: { location_sharing_permission: false },
  })

  const email = watch('email')
  const locationPermission = watch('location_sharing_permission')

  const handleLocationToggle = async (checked) => {
    setLocationError('')
    if (!checked) {
      setValue('location_sharing_permission', false, { shouldValidate: true })
      return
    }
    try {
      await requestLocation()
      setValue('location_sharing_permission', true, { shouldValidate: true })
    } catch {
      setValue('location_sharing_permission', false, { shouldValidate: true })
      setLocationError(
        'We could not access your location. Please allow location access in your browser to continue -- it is required to register.',
      )
    }
  }

  const canSubmit = isValid && emailVerified && !!coordinates && locationPermission

  const onSubmit = async (values) => {
    setApiError('')
    try {
      const user = await registerUser({
        role,
        first_name: values.first_name,
        last_name: values.last_name,
        age: Number(values.age),
        blood_group: values.blood_group,
        contact: values.contact,
        email: values.email,
        address: {
          address_line: values.address_line,
          postcode: values.postcode,
          city_town: values.city_town,
        },
        location_sharing_permission: true,
        location: coordinates,
        password: values.password,
        confirm_password: values.confirm_password,
      })
      navigate(user.role === 'donor' ? '/donor/dashboard' : '/recipient/dashboard', { replace: true })
    } catch (err) {
      setApiError(getApiErrorMessage(err))
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-5" noValidate>
        {apiError && <Alert variant="error">{apiError}</Alert>}

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
          <Input id="contact" label="Contact number" required placeholder="+91XXXXXXXXXX" error={errors.contact?.message} {...register('contact')} />
          <Input id="email" label="Email" type="email" required error={errors.email?.message} {...register('email')} />
        </div>

        <div>
          <p className="text-sm font-medium text-ink-800 mb-1.5">
            Email verification <span className="text-crimson-500">*</span>
          </p>
          <OtpVerification
            email={email}
            purpose="registration"
            verified={emailVerified}
            onVerified={() => setEmailVerified(true)}
            disabled={!!errors.email || !email}
          />
        </div>

        <div className="border-t border-ink-100 pt-5">
          <p className="text-sm font-semibold text-ink-900 mb-3">Address</p>
          <div className="space-y-4">
            <Input id="address_line" label="Address line" required error={errors.address_line?.message} {...register('address_line')} />
            <div className="grid sm:grid-cols-2 gap-4">
              <Input id="postcode" label="Postcode" required error={errors.postcode?.message} {...register('postcode')} />
              <Input id="city_town" label="City / Town" required error={errors.city_town?.message} {...register('city_town')} />
            </div>
          </div>
        </div>

        <div className="border-t border-ink-100 pt-5">
          <Checkbox
            label="I agree to share my precise location with LifeLine so it can connect me with nearby matches."
            checked={!!locationPermission}
            onChange={(e) => handleLocationToggle(e.target.checked)}
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

        <div className="border-t border-ink-100 pt-5 space-y-4">
          <Input
            id="password"
            label="Password"
            type="password"
            required
            hint="At least 8 characters, with uppercase, lowercase, a digit, and a special character."
            error={errors.password?.message}
            {...register('password')}
          />
          <Input
            id="confirm_password"
            label="Confirm password"
            type="password"
            required
            error={errors.confirm_password?.message}
            {...register('confirm_password')}
          />
        </div>

        <Button type="submit" fullWidth size="lg" isLoading={isSubmitting} disabled={!canSubmit}>
          Create account
        </Button>
        {!canSubmit && !isSubmitting && (
          <p className="text-xs text-ink-400 text-center">
            Complete all fields, verify your email, and grant location access to continue.
          </p>
        )}
      </form>
    </Card>
  )
}
