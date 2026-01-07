import api from './api'
import { User } from '../types/user'

export interface TelegramAuthData {
  id: number
  first_name: string
  last_name?: string
  username?: string
  auth_date: number
  hash: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export const authApi = {
  // Авторизация через Telegram
  loginWithTelegram: async (data: TelegramAuthData): Promise<AuthResponse> => {
    const response = await api.post<AuthResponse>('/auth/telegram', data)
    // Сохраняем токен
    localStorage.setItem('access_token', response.data.access_token)
    return response.data
  },

  // Получить текущего пользователя
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me')
    return response.data
  },

  // Выход
  logout: (): void => {
    localStorage.removeItem('access_token')
  },
}
