import { z } from 'zod'
/** Contract: password >= 10 chars, at least one letter and one digit. */
export const passwordSchema = z.string().min(10, 'Use at least 10 characters').regex(/[A-Za-z]/, 'Include a letter').regex(/\d/, 'Include a digit')
