import api from './api'

export interface ActivityItem {
  id: string
  action: string
  message: string
  user_name?: string
  timestamp: string
  details?: any
}

export interface ActivityFeed {
  items: ActivityItem[]
  total: number
  skip: number
  limit: number
  period_days: number
}

export const activityApi = {
  getFeed: async (params?: {
    skip?: number
    limit?: number
    days?: number
  }): Promise<ActivityFeed> => {
    const response = await api.get<ActivityFeed>('/activity/feed', { params })
    return response.data
  },

  getRecent: async (limit?: number): Promise<ActivityItem[]> => {
    const response = await api.get<ActivityItem[]>('/activity/recent', { params: { limit } })
    return response.data
  },
}
