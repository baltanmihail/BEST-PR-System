import api from './api'

export interface DailyTask {
  id: string
  title: string
  notes?: string
  date: string
  scheduled_time?: string | null
  priority: number
  is_done: boolean
  done_at?: string
  creator_id: string
  assignee_id: string
  creator_name?: string
  assignee_name?: string
  created_at?: string
}

export interface DailyTaskCreate {
  title: string
  notes?: string
  date?: string
  scheduled_time?: string
  priority?: number
  assignee_id?: string
}

export interface DailyTaskUpdate {
  title?: string
  notes?: string
  is_done?: boolean
  date?: string
  scheduled_time?: string | null
  priority?: number
  assignee_id?: string
}

export interface DailyTaskStats {
  date: string
  total: number
  done: number
  pending: number
}

export const dailyTasksApi = {
  getTasks: async (params?: { target_date?: string; assignee_id?: string; include_done?: boolean }): Promise<DailyTask[]> => {
    const response = await api.get<DailyTask[]>('/daily-tasks', { params })
    return response.data
  },

  getMyTasks: async (target_date?: string): Promise<DailyTask[]> => {
    const response = await api.get<DailyTask[]>('/daily-tasks/my', { params: { target_date } })
    return response.data
  },

  create: async (data: DailyTaskCreate): Promise<DailyTask> => {
    const response = await api.post<DailyTask>('/daily-tasks', data)
    return response.data
  },

  update: async (id: string, data: DailyTaskUpdate): Promise<DailyTask> => {
    const response = await api.patch<DailyTask>(`/daily-tasks/${id}`, data)
    return response.data
  },

  delete: async (id: string): Promise<void> => {
    await api.delete(`/daily-tasks/${id}`)
  },

  getStats: async (target_date?: string): Promise<DailyTaskStats> => {
    const response = await api.get<DailyTaskStats>('/daily-tasks/stats', { params: { target_date } })
    return response.data
  },
}
