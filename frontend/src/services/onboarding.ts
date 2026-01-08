import api from './api'

export interface InitVisitResponse {
  success: boolean
  created: boolean
  first_visit_at?: string
  last_visit_at?: string
}

export interface TrackTimeRequest {
  telegram_id: string
  time_seconds: number
}

export interface TrackTimeResponse {
  success: boolean
  total_time_seconds: number
  should_send_reminder: boolean
  reminder_id: string
}

export const onboardingApi = {
  /**
   * Инициализировать визит пользователя на сайте
   */
  initVisit: async (telegram_id: string): Promise<InitVisitResponse> => {
    const response = await api.post(`/onboarding/init-visit?telegram_id=${telegram_id}`)
    return response.data
  },

  /**
   * Отслеживание времени, проведённого на сайте
   */
  trackTime: async (data: TrackTimeRequest): Promise<TrackTimeResponse> => {
    const response = await api.post('/onboarding/track-time', data)
    return response.data
  },
}
