import api from './api'

export interface QRGenerateResponse {
  session_id: string
  qr_code: string  // Base64 encoded image
  session_token: string
  expires_at: string
}

export interface QRStatusResponse {
  status: 'pending' | 'confirmed' | 'expired' | 'cancelled'
  session_id: string
  session_token?: string
  access_token?: string
  user?: {
    id: string
    telegram_id: number
    username?: string
    full_name: string
    is_active: boolean
    role: string
  }
}

export const qrAuthApi = {
  // Генерация QR-кода
  generate: async (): Promise<QRGenerateResponse> => {
    const response = await api.post<QRGenerateResponse>('/auth/qr/generate')
    return response.data
  },

  // Проверка статуса
  getStatus: async (session_token: string): Promise<QRStatusResponse> => {
    const response = await api.get<QRStatusResponse>(`/auth/qr/status/${session_token}`)
    return response.data
  },
}
