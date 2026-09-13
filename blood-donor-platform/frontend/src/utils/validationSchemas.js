import * as yup from 'yup'
import { BLOOD_GROUPS } from './bloodGroups'

const NAME_PATTERN = /^[A-Za-z][A-Za-z\s'-]{0,79}$/
const CONTACT_PATTERN = /^\+?[0-9]{7,15}$/
// Mirrors the backend's strong-password rule: 8+ chars, upper, lower, digit, special char.
const PASSWORD_PATTERN = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w\s]).{8,}$/

const nameField = (label) =>
  yup
    .string()
    .trim()
    .required(`${label} is required.`)
    .matches(NAME_PATTERN, `${label} may only contain letters, spaces, hyphens, and apostrophes.`)

export const registerSchema = yup.object({
  first_name: nameField('First name'),
  last_name: nameField('Last name'),
  age: yup
    .number()
    .typeError('Age must be a number.')
    .required('Age is required.')
    .min(18, 'You must be at least 18 years old to register.')
    .max(100, 'Please enter a valid age.'),
  blood_group: yup.string().oneOf(BLOOD_GROUPS, 'Select a valid blood group.').required('Blood group is required.'),
  contact: yup
    .string()
    .trim()
    .required('Contact number is required.')
    .matches(CONTACT_PATTERN, 'Enter a valid contact number (7-15 digits, optional + prefix).'),
  email: yup.string().trim().email('Enter a valid email address.').required('Email is required.'),
  address_line: yup.string().trim().min(3, 'Address is too short.').required('Address is required.'),
  postcode: yup.string().trim().min(3, 'Enter a valid postcode.').required('Postcode is required.'),
  city_town: yup.string().trim().min(2, 'Enter a valid city/town.').required('City/Town is required.'),
  location_sharing_permission: yup
    .boolean()
    .oneOf([true], 'Location sharing permission is mandatory to register.'),
  password: yup
    .string()
    .required('Password is required.')
    .matches(
      PASSWORD_PATTERN,
      'Password must be 8+ characters and include an uppercase letter, a lowercase letter, a digit, and a special character.',
    ),
  confirm_password: yup
    .string()
    .required('Please confirm your password.')
    .oneOf([yup.ref('password')], 'Password and Confirm Password must match.'),
})

export const loginSchema = yup.object({
  email: yup.string().trim().email('Enter a valid email address.').required('Email is required.'),
  password: yup.string().required('Password is required.'),
})

export const bloodRequestOtherSchema = yup.object({
  first_name: nameField('First name'),
  last_name: nameField('Last name'),
  age: yup.number().typeError('Age must be a number.').required('Age is required.').min(0).max(120),
  blood_group: yup.string().oneOf(BLOOD_GROUPS, 'Select a valid blood group.').required('Blood group is required.'),
  contact: yup
    .string()
    .trim()
    .required('Contact number is required.')
    .matches(CONTACT_PATTERN, 'Enter a valid contact number (7-15 digits, optional + prefix).'),
  email: yup.string().trim().email('Enter a valid email address.').required('Email is required.'),
  address_line: yup.string().trim().min(3, 'Address is too short.').required('Address is required.'),
  postcode: yup.string().trim().min(3, 'Enter a valid postcode.').required('Postcode is required.'),
  city_town: yup.string().trim().min(2, 'Enter a valid city/town.').required('City/Town is required.'),
})
