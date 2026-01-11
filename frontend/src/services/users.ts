import api from './api'
import { Task, TaskAssignment } from '../types/task'

export interface ProfileUpdate {
  full_name?: string
  bio?: string
  contacts?: {
    email?: string
    phone?: string
    telegram?: string
    vk?: string
    instagram?: string
  }
  skills?: string[]
  portfolio?: Array<{
    title: string
    description?: string
    url: string
    type: 'photo' | 'video' | 'link'
    gallery_item_id?: string
  }>
}

export interface UserProfile {
  id: string
  telegram_id: number
  username?: string
  telegram_username?: string
  email?: string
  full_name: string
  role: string
  level: number
  points: number
  streak_days: number
  last_activity_at?: string
  created_at: string
  updated_at: string
  is_active: boolean
  avatar_url?: string
  bio?: string
  contacts?: {
    email?: string
    phone?: string
    telegram?: string
    vk?: string
    instagram?: string
  }
  skills?: string[]
  portfolio?: Array<{
    title: string
    description?: string
    url: string
    type: 'photo' | 'video' | 'link'
    gallery_item_id?: string
  }>
}

export interface UserActivity {
  id: string
  user_id: string
  action_type: string
  details?: Record<string, any>
  created_at: string
}

export interface UserListResponse {
  items: UserProfile[]
  total: number
  skip: number
  limit: number
}

export interface UserActivityResponse {
  items: UserActivity[]
  total: number
  skip: number
  limit: number
}

export interface UserTasksResponse {
  active: Array<{
    task: Task
    assignment: TaskAssignment
  }>
  completed: Array<{
    task: Task
    assignment: TaskAssignment
  }>
  total: number
}

export const usersApi = {
  getMyProfile: async (): Promise<UserProfile> => {
    const response = await api.get<UserProfile>('/users/me')
    return response.data
  },

  updateProfile: async (data: ProfileUpdate): Promise<UserProfile> => {
    const response = await api.put<UserProfile>('/users/me', data)
    return response.data
  },

  uploadPhoto: async (file: File): Promise<UserProfile> => {
    const formData = new FormData()
    formData.append('photo', file)
    const response = await api.post<UserProfile>('/users/me/photo', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  getUsers: async (params?: {
    skip?: number
    limit?: number
    search?: string
    role?: string
    is_active?: boolean
  }): Promise<UserListResponse> => {
    const response = await api.get<UserListResponse>('/users', { params })
    return response.data
  },

  getUser: async (userId: string): Promise<UserProfile> => {
    const response = await api.get<UserProfile>(`/users/${userId}`)
    return response.data
  },

  getUserActivity: async (
    userId: string,
    params?: {
      skip?: number
      limit?: number
    }
  ): Promise<UserActivityResponse> => {
    const response = await api.get<UserActivityResponse>(`/users/${userId}/activity`, { params })
    return response.data
  },

  getUserTasks: async (userId: string): Promise<UserTasksResponse> => {
    const response = await api.get<UserTasksResponse>(`/users/${userId}/tasks`)
    return response.data
  },

  updateUser: async (userId: string, data: Partial<UserProfile>): Promise<UserProfile> => {
    const response = await api.put<UserProfile>(`/users/${userId}`, data)
    return response.data
  },

  blockUser: async (userId: string, reason?: string): Promise<UserProfile> => {
    const response = await api.post<UserProfile>(`/users/${userId}/block`, { reason })
    return response.data
  },

  unblockUser: async (userId: string): Promise<UserProfile> => {
    const response = await api.post<UserProfile>(`/users/${userId}/unblock`)
    return response.data
  },

  adjustPoints: async (userId: string, points: number, reason: string): Promise<UserProfile> => {
    const formData = new FormData()
    formData.append('points_delta', points.toString())
    if (reason) {
      formData.append('reason', reason)
    }
    const response = await api.post<UserProfile>(`/users/${userId}/points`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },

  exportUserData: async (userId: string): Promise<Blob> => {
    const response = await api.get(`/users/${userId}/export`, {
      responseType: 'blob',
    })
    return response.data
  },
}
