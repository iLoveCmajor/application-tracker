// The single entry point for backend calls. Components import `api` from here and never call fetch directly.

import { createHttpApi } from './http'
import type { Api } from './types'

export const api: Api = createHttpApi(import.meta.env.VITE_API_BASE_URL ?? '/api/v1')

export { ApiError, errorMessage } from './errors'
export type { ErrorCode } from './errors'
export * from './types'
