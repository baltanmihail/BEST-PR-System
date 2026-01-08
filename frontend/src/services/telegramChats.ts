import { api } from './api'

export const telegramChatsApi = {
  /**
   * Получить информацию об общем чате
   */
  getGeneralChat: async () => {
    const response = await api.get('/telegram-chats/general')
    return response.data
  },

  /**
   * Получить информацию о чате для задачи
   */
  getTaskChat: async (taskId: string) => {
    const response = await api.get(`/telegram-chats/task/${taskId}`)
    return response.data
  },
}
