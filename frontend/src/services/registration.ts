import api from './api'
import { TelegramAuthData } from './auth'

export interface RegistrationRequest {
  telegram_auth: TelegramAuthData
  personal_data_consent: {
    consent: boolean
    consent_date?: string
  }
  user_agreement: {
    accepted: boolean
    version?: string
  }
}

export interface UserAgreement {
  version: string
  title: string
  content: string
  updated_at: string
}

export const registrationApi = {
  register: async (data: RegistrationRequest): Promise<{
    access_token: string
    token_type: string
    user: any
    message: string
  }> => {
    const response = await api.post('/registration/register', data)
    return response.data
  },

  getAgreement: async (): Promise<UserAgreement> => {
    const response = await api.get<UserAgreement>('/registration/agreement')
    return response.data
  },
}
