import { api } from './api'

export const tourApi = {
  /**
   * Получить статус прохождения гайда
   */
  getStatus: async () => {
    const response = await api.get('/tour/status')
    return response.data
  },

  /**
   * Отметить гайд как пройденный
   */
  complete: async () => {
    const response = await api.post('/tour/complete')
    return response.data
  },

  /**
   * Сбросить статус прохождения гайда
   */
  reset: async () => {
    const response = await api.post('/tour/reset')
    return response.data
  },
}
