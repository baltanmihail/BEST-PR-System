import api from './api'

export interface PublicTask {
  id: string
  title: string
  type: string
  priority: string
  status: string
  due_date_relative: string
  due_date?: string | null
  participants_count: number
  stages_count: number
  coordinator_name: string
  created_at?: string | null
}

export interface PublicLeaderboardUser {
  rank: number
  name: string
  username: string | null
  level: number
  points: number
  completed_tasks: number
  role?: string
}

export interface PublicStats {
  completed_tasks: number
  active_tasks: number
  participants_count: number
  average_points: number
}

export interface PublicTasksResponse {
  items: PublicTask[]
  total: number
  skip: number
  limit: number
}

export const publicApi = {
  // Публичные задачи
  getTasks: async (params?: {
    skip?: number
    limit?: number
    task_type?: string
  }): Promise<PublicTasksResponse> => {
    const response = await api.get<PublicTasksResponse>('/public/tasks', { params })
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
