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
  // urlParams - опциональные параметры для передачи в query string (например, "?from=bot&telegram_id=123")
  generate: async (urlParams: string = ''): Promise<QRGenerateResponse> => {
    try {
      const endpoint = '/auth/qr/generate' + urlParams
      const response = await api.post<QRGenerateResponse>(endpoint)
      console.log('QR generate response:', response.data)
      
      // Проверяем, что qr_code присутствует и имеет правильный формат
      if (!response.data.qr_code) {
        throw new Error('QR code not found in response')
      }
      
      if (!response.data.qr_code.startsWith('data:image/')) {
        throw new Error('Invalid QR code format')
      }
      
      return response.data
    } catch (error: any) {
      console.error('QR generate error:', error)
      console.error('Error response:', error.response?.data)
      throw error
    }
  },

  // Проверка статуса
  getStatus: async (session_token: string): Promise<QRStatusResponse> => {
    try {
      const response = await api.get<QRStatusResponse>(`/auth/qr/status/${session_token}`)
      return response.data
    } catch (error: any) {
      console.error('QR status error:', error)
      throw error
    }
  },
}
