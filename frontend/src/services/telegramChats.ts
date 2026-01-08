import api from './api'

export interface GeneralChatResponse {
  exists: boolean
  chat_id?: string
  chat_name?: string
  chat_type?: string
  invite_link?: string
  is_active?: boolean
  message?: string
}

export interface TaskChatResponse {
  exists: boolean
  topic_id?: number
  topic_name?: string
  invite_link?: string
  is_open_topic?: boolean
  message?: string
}

export const telegramChatsApi = {
  /**
   * Получить информацию об общем чате
   */
  getGeneralChat: async (): Promise<GeneralChatResponse> => {
    const response = await api.get('/telegram-chats/general')
    return response.data
  },

  /**
   * Получить информацию о чате для задачи
   */
  getTaskChat: async (taskId: string): Promise<TaskChatResponse> => {
    const response = await api.get(`/telegram-chats/task/${taskId}`)
    return response.data
  },
}
