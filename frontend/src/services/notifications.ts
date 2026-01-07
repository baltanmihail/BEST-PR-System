import api from './api'

export interface Notification {
  id: string
  type: string
  title: string
  message: string
  data: any
  is_read: boolean
  is_important?: boolean
  created_at: string
}

export interface NotificationsResponse {
  items: Notification[]
  important: Notification[]
  regular: Notification[]
  total: number
  unread_count: number
  important_count: number
  skip: number
  limit: number
}

export const notificationsApi = {
  getNotifications: async (params?: {
    unread_only?: boolean
    important_only?: boolean
    skip?: number
    limit?: number
  }): Promise<NotificationsResponse> => {
    const response = await api.get<NotificationsResponse>('/notifications', { params })
    return response.data
  },

  getUnreadCount: async (): Promise<{ unread_count: number; important_unread_count: number }> => {
    const response = await api.get<{ unread_count: number; important_unread_count: number }>('/notifications/unread-count')
    return response.data
  },

  markAsRead: async (notificationId: string): Promise<void> => {
    await api.patch(`/notifications/${notificationId}/read`)
  },

  markAllAsRead: async (): Promise<{ marked_count: number; message: string }> => {
    const response = await api.post<{ marked_count: number; message: string }>('/notifications/mark-all-read')
    return response.data
  },
}
