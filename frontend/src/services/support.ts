import api from './api'

export interface SupportRequest {
  message: string
  contact?: string
  category?: string
  link?: string
  file?: File
}

export const supportApi = {
  createRequest: async (request: SupportRequest): Promise<{ status: string; message: string; file_id?: string }> => {
    // Используем FormData для поддержки загрузки файлов
    const formData = new FormData()
    formData.append('message', request.message)
    if (request.contact) {
      formData.append('contact', request.contact)
    }
    if (request.category) {
      formData.append('category', request.category)
    }
    if (request.link) {
      formData.append('link', request.link)
    }
    if (request.file) {
      formData.append('file', request.file)
    }

    const response = await api.post<{ status: string; message: string; file_id?: string }>('/support/request', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
}
