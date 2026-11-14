// Error codes from openapi.yaml, plus `network_error` for when the server can't be reached.
export type ErrorCode =
  | 'validation_error'
  | 'not_found'
  | 'invalid_transition'
  | 'service_unavailable'
  | 'internal_error'
  | 'network_error'

export class ApiError extends Error {
  readonly status: number
  readonly code: ErrorCode
  readonly details: Record<string, unknown>

  constructor(status: number, code: ErrorCode, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Something went wrong'
}
