import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { yupResolver } from '@hookform/resolvers/yup'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Droplet } from 'lucide-react'
import Layout from '../components/layout/Layout.jsx'
import Card from '../components/common/Card.jsx'
import Input from '../components/common/Input.jsx'
import Button from '../components/common/Button.jsx'
import Alert from '../components/common/Alert.jsx'
import { useAuth } from '../hooks/useAuth'
import { loginSchema } from '../utils/validationSchemas'
import { getApiErrorMessage } from '../api/axiosInstance'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [apiError, setApiError] = useState('')

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: yupResolver(loginSchema) })

  const onSubmit = async (values) => {
    setApiError('')
    try {
      const user = await login(values.email, values.password)
      const redirectTo =
        location.state?.from?.pathname || (user.role === 'donor' ? '/donor/dashboard' : '/recipient/dashboard')
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setApiError(getApiErrorMessage(err))
    }
  }

  return (
    <Layout>
      <section className="max-w-md mx-auto px-5 py-16 sm:py-24">
        <div className="text-center mb-8">
          <span className="inline-flex w-12 h-12 rounded-2xl bg-teal-500 items-center justify-center mb-4">
            <Droplet className="w-6 h-6 text-white" fill="white" fillOpacity={0.25} />
          </span>
          <h1 className="text-2xl font-display font-bold text-ink-900">Welcome back</h1>
          <p className="text-ink-500 text-sm mt-1.5">Log in to your LifeLine account.</p>
        </div>

        <Card>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            {apiError && <Alert variant="error">{apiError}</Alert>}
            <Input
              id="email"
              label="Email"
              type="email"
              required
              autoComplete="email"
              error={errors.email?.message}
              {...register('email')}
            />
            <Input
              id="password"
              label="Password"
              type="password"
              required
              autoComplete="current-password"
              error={errors.password?.message}
              {...register('password')}
            />
            <Button type="submit" fullWidth isLoading={isSubmitting}>
              Log in
            </Button>
          </form>
        </Card>

        <p className="text-center text-sm text-ink-500 mt-6">
          Don't have an account?{' '}
          <Link to="/register" className="text-teal-600 font-medium hover:underline">
            Register
          </Link>
        </p>
      </section>
    </Layout>
  )
}
