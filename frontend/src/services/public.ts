import api from './api'

export interface PublicTask {
  id: string
  title: string
  type: string
  priority: string
  due_date_relative: string
  participants_count: number
  stages_count: number
  coordinator_name: string
}

export interface PublicLeaderboardUser {
  rank: number
  name: string
  username: string | null
  level: number
  points: number
  completed_tasks: number
}

export interface PublicStats {
  completed_tasks: number
  active_tasks: number
  participants_count: number
  average_points: number
}

export const publicApi = {
  // Публичные задачи
  getTasks: async (params?: {
    skip?: number
    limit?: number
    task_type?: string
  }): Promise<PublicTask[]> => {
    const response = await api.get<PublicTask[]>('/public/tasks', { params })
    return response.data
  },

  getTask: async (taskId: string): Promise<PublicTask> => {
    const response = await api.get<PublicTask>(`/public/tasks/${taskId}`)
    return response.data
  },

  // Топ пользователей
  getLeaderboard: async (): Promise<PublicLeaderboardUser[]> => {
    const response = await api.get<PublicLeaderboardUser[]>('/public/leaderboard')
    return response.data
  },

  // Статистика
  getStats: async (): Promise<PublicStats> => {
    const response = await api.get<PublicStats>('/public/stats')
    return response.data
  },
}
