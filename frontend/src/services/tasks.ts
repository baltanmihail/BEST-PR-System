import api from './api'
import { Task, TaskCreate, TaskUpdate, TasksResponse } from '../types/task'
import { TaskQuestion } from '../types/task_question'

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

  // Вопросы к задачам
  getTaskQuestions: async (taskId: string): Promise<TaskQuestion[]> => {
    const response = await api.get<TaskQuestion[]>(`/tasks/${taskId}/questions`)
    return response.data
  },

  createTaskQuestion: async (taskId: string, question: string): Promise<TaskQuestion> => {
    const response = await api.post<TaskQuestion>(`/tasks/${taskId}/questions`, { question })
    return response.data
  },

  answerTaskQuestion: async (taskId: string, questionId: string, answer: string): Promise<TaskQuestion> => {
    const response = await api.post<TaskQuestion>(`/tasks/${taskId}/questions/${questionId}/answer`, { answer })
    return response.data
  },

  // Файлы задач
  getTaskFiles: async (taskId: string) => {
    const response = await api.get(`/tasks/${taskId}/files`)
    return response.data
  },
}
