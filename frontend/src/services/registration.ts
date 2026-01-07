import api from './api'

export interface RegistrationRequest {
  telegram_auth: {
    id: number
    first_name: string
    last_name?: string
    username?: string
    photo_url?: string
    auth_date: number
    hash: string
  }
  personal_data_consent: {
    consent: boolean
    date: string
  }
  user_agreement: {
    accepted: boolean
    version: string
  }
}

export interface AgreementResponse {
  version: string
  title: string
  content: string
  updated_at: string
}

export const registrationApi = {
  register: async (data: RegistrationRequest) => {
    const response = await api.post('/registration/register', data)
    return response.data
  },

  getAgreement: async (): Promise<AgreementResponse> => {
    const response = await api.get<AgreementResponse>('/registration/agreement')
    return response.data
  },
}
