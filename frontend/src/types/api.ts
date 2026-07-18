export interface ApiResponse<T> {
  request_id: string
  success: boolean
  message: string
  data: T
}

export interface ApiErrorData {
  error_code: string
  detail: string
}

export interface RequestState {
  loading: boolean
  error: string
}

