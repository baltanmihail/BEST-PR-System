import api from './api'
import { Task, TaskCreate, TaskUpdate, TasksResponse } from '../types/task'

export const tasksApi = {
  // Получить список задач
  getTasks: async (params?: {
    skip?: number
    limit?: number
    task_type?: string
    status?: string
    priority?: string
  }): Promise<TasksResponse> => {
    const response = await api.get<TasksResponse>('/tasks', { params })
    return response.data
  },

  // Получить задачу по ID
  getTask: async (id: string): Promise<Task> => {
    const response = await api.get<Task>(`/tasks/${id}`)
    return response.data
  },

  // Создать задачу
  createTask: async (data: TaskCreate): Promise<Task> => {
    const response = await api.post<Task>('/tasks', data)
    return response.data
  },

  // Обновить задачу
  updateTask: async (id: string, data: TaskUpdate): Promise<Task> => {
    const response = await api.patch<Task>(`/tasks/${id}`, data)
    return response.data
  },

  // Удалить задачу
  deleteTask: async (id: string): Promise<void> => {
    await api.delete(`/tasks/${id}`)
  },
}
