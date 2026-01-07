import api from './api'

export interface UserStats {
  level: number
  points: number
  streak_days: number
  completed_tasks: number
  total_tasks: number
  next_level_points: number
  current_level_points: number
  achievements?: any[]
}

export interface LeaderboardUser {
  rank: number
  name: string
  username: string | null
  level: number
  points: number
  completed_tasks: number
}

export interface Achievement {
  id: string
  type: string
  name: string
  unlocked_at: string
}

export const gamificationApi = {
  getMyStats: async (): Promise<UserStats> => {
    const response = await api.get<UserStats>('/gamification/stats')
    return response.data
  },

  getLeaderboard: async (limit: number = 10): Promise<LeaderboardUser[]> => {
    const response = await api.get<LeaderboardUser[]>('/gamification/leaderboard', {
      params: { limit },
    })
    return response.data
  },

  getMyAchievements: async (): Promise<Achievement[]> => {
    const response = await api.get<Achievement[]>('/gamification/achievements')
    return response.data
  },
}
