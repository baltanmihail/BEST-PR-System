import api from './api'

export interface SupportRequest {
  message: string
  contact?: string
  category?: string
  link?: string
  file?: File
}

export interface SupportTicket {
  id: string
  user_name: string
  user_telegram_id: number | null
  contact: string
  category: string
  message: string
  is_read: boolean
  created_at: string | null
}

export interface SupportReplyRequest {
  user_telegram_id: number
  user_name: string
  message: string
}

export const supportApi = {
  createRequest: async (request: SupportRequest): Promise<{ status: string; message: string; file_id?: string }> => {
    const formData = new FormData()
    formData.append('message', request.message)
    if (request.contact) formData.append('contact', request.contact)
    if (request.category) formData.append('category', request.category)
    if (request.link) formData.append('link', request.link)
    if (request.file) formData.append('file', request.file)

    const response = await api.post<{ status: string; message: string; file_id?: string }>('/support/request', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  getTickets: async (limit = 50): Promise<{ items: SupportTicket[] }> => {
    const response = await api.get<{ items: SupportTicket[] }>('/support/tickets', { params: { limit } })
    return response.data
  },

  reply: async (data: SupportReplyRequest): Promise<{ status: string; message: string }> => {
    const response = await api.post<{ status: string; message: string }>('/support/reply', data)
    return response.data
  },
}
