import api from './api'
import { Task, TaskCreate, TaskUpdate, TasksResponse, TaskAssignment, TaskStage, TaskStageCreate, TaskStageUpdate } from '../types/task'
import { TaskQuestion } from '../types/task_question'

export const tasksApi = {
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

  getTask: async (id: string): Promise<Task> => {
    const response = await api.get<Task>(`/tasks/${id}`)
    return response.data
  },

  createTask: async (data: TaskCreate): Promise<Task> => {
    const response = await api.post<Task>('/tasks', data)
    return response.data
  },

  updateTask: async (id: string, data: TaskUpdate): Promise<Task> => {
    const response = await api.patch<Task>(`/tasks/${id}`, data)
    return response.data
  },

  deleteTask: async (id: string): Promise<void> => {
    await api.delete(`/tasks/${id}`)
  },

  // === Назначения ===

  assignTask: async (taskId: string): Promise<{ status: string }> => {
    const response = await api.post(`/tasks/${taskId}/assign`)
    return response.data
  },

  assignUserToTask: async (taskId: string, userId: string, role?: string): Promise<{ status: string }> => {
    const response = await api.post(`/tasks/${taskId}/assign-user`, { user_id: userId, role })
    return response.data
  },

  getAssignments: async (taskId: string): Promise<TaskAssignment[]> => {
    const response = await api.get<TaskAssignment[]>(`/tasks/${taskId}/assignments`)
    return response.data
  },

  cancelAssignment: async (taskId: string, assignmentId: string): Promise<void> => {
    await api.delete(`/tasks/${taskId}/assignments/${assignmentId}`)
  },

  updateAssignment: async (taskId: string, assignmentId: string, data: { status?: string; role_in_task?: string }): Promise<TaskAssignment> => {
    const response = await api.patch<TaskAssignment>(`/tasks/${taskId}/assignments/${assignmentId}`, data)
    return response.data
  },

  reassignTask: async (taskId: string, newUserId: string, role?: string): Promise<{ status: string }> => {
    const response = await api.post(`/tasks/${taskId}/reassign`, { new_user_id: newUserId, role })
    return response.data
  },

  completeTask: async (taskId: string): Promise<Task> => {
    const response = await api.post<Task>(`/tasks/${taskId}/complete`)
    return response.data
  },

  // === Вопросы ===

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

  // === Этапы ===

  getStages: async (taskId: string): Promise<TaskStage[]> => {
    const response = await api.get<TaskStage[]>(`/tasks/${taskId}/stages`)
    return response.data
  },

  createStage: async (taskId: string, data: TaskStageCreate): Promise<TaskStage> => {
    const response = await api.post<TaskStage>(`/tasks/${taskId}/stages`, data)
    return response.data
  },

  updateStage: async (taskId: string, stageId: string, data: TaskStageUpdate): Promise<TaskStage> => {
    const response = await api.patch<TaskStage>(`/tasks/${taskId}/stages/${stageId}`, data)
    return response.data
  },

  deleteStage: async (taskId: string, stageId: string): Promise<void> => {
    await api.delete(`/tasks/${taskId}/stages/${stageId}`)
  },

  // === Файлы ===

  getTaskFiles: async (taskId: string) => {
    const response = await api.get(`/tasks/${taskId}/files`)
    return response.data
  },
}
