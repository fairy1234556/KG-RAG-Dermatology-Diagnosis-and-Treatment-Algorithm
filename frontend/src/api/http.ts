import axios, { AxiosError } from 'axios'

import type { ApiResponse } from '@/types/api'

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000
})

export async function requestData<T>(promise: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  try {
    const response = await promise
    if (!response.data.success) {
      throw new Error(response.data.message || '请求失败')
    }
    return response.data.data
  } catch (error) {
    if (error instanceof AxiosError) {
      const payload = error.response?.data as ApiResponse<unknown> | undefined
      throw new Error(payload?.message || '无法连接后端服务，请确认 FastAPI 已启动')
    }
    if (error instanceof Error) {
      throw error
    }
    throw new Error('请求失败，请稍后重试')
  }
}

