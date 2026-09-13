import { Routes, Route } from 'react-router-dom'
import Home from '../pages/Home.jsx'
import About from '../pages/About.jsx'
import Login from '../pages/Login.jsx'
import Register from '../pages/Register.jsx'
import RegisterDonor from '../pages/RegisterDonor.jsx'
import RegisterRecipient from '../pages/RegisterRecipient.jsx'
import DonorDashboard from '../pages/DonorDashboard.jsx'
import RecipientDashboard from '../pages/RecipientDashboard.jsx'
import BloodRequestForm from '../pages/BloodRequestForm.jsx'
import NotFound from '../pages/NotFound.jsx'
import ProtectedRoute from '../components/auth/ProtectedRoute.jsx'

export default function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/about" element={<About />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/register/donor" element={<RegisterDonor />} />
      <Route path="/register/recipient" element={<RegisterRecipient />} />

      <Route
        path="/donor/dashboard"
        element={
          <ProtectedRoute allowedRoles={['donor']}>
            <DonorDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recipient/dashboard"
        element={
          <ProtectedRoute allowedRoles={['recipient']}>
            <RecipientDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/blood-request/new"
        element={
          <ProtectedRoute allowedRoles={['recipient']}>
            <BloodRequestForm />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
