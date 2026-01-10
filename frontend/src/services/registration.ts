import api from './api'

export interface RegistrationRequest {
  telegram_auth?: {  // Опционально для QR-регистрации
    id: number
    first_name: string
    last_name?: string
    username?: string
    photo_url?: string
    auth_date: number
    hash: string  // Для QR-регистрации может быть пустой строкой, но для обычной обязателен
  }
  personal_data_consent: {
    consent: boolean
    consent_date: string
  }
  user_agreement: {
    accepted: boolean
    version: string
  }
  qr_token?: string  // Опциональный токен QR-сессии для упрощённой регистрации
}

export interface AgreementResponse {
  version: string
  title: string
  content: string
  updated_at: string
}

export interface RegistrationCodeRequest {
  telegram_id?: number
  telegram_username?: string
}

export interface RegistrationCodeResponse {
  message: string
  expires_in_minutes: number
}

export interface RegistrationWithCodeRequest {
  code: string
  personal_data_consent: {
    consent: boolean
    consent_date: string
  }
  user_agreement: {
    accepted: boolean
    version: string
  }
}

export const registrationApi = {
  register: async (data: RegistrationRequest) => {
    const response = await api.post('/registration/register', data)
    return response.data
  },

  requestCode: async (data: RegistrationCodeRequest): Promise<RegistrationCodeResponse> => {
    const response = await api.post<RegistrationCodeResponse>('/registration/request-code', data)
    return response.data
  },

  registerWithCode: async (data: RegistrationWithCodeRequest) => {
    const response = await api.post('/registration/register-with-code', data)
    return response.data
  },

  getAgreement: async (): Promise<AgreementResponse> => {
    const response = await api.get<AgreementResponse>('/registration/agreement')
    return response.data
  },
}
