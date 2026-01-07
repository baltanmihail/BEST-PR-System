import api from './api'

export interface SupportRequest {
  message: string
  contact?: string
  category?: string
}

export const supportApi = {
  createRequest: async (request: SupportRequest): Promise<{ status: string; message: string }> => {
    const response = await api.post<{ status: string; message: string }>('/support/request', request)
    return response.data
  },
}
