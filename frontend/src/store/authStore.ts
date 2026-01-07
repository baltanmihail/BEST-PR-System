import { create } from 'zustand'
import { User } from '../types/user'
import { authApi } from '../services/auth'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (telegramData: any) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,

  login: async (telegramData) => {
    set({ isLoading: true })
    try {
      const response = await authApi.loginWithTelegram(telegramData)
      set({ user: response.user, isAuthenticated: true, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  logout: () => {
    authApi.logout()
    set({ user: null, isAuthenticated: false })
  },

  fetchUser: async () => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      set({ isAuthenticated: false, user: null })
      return
    }

    set({ isLoading: true })
    try {
      const user = await authApi.getMe()
      set({ user, isAuthenticated: true, isLoading: false })
    } catch (error) {
      set({ isAuthenticated: false, user: null, isLoading: false })
      authApi.logout()
    }
  },
}))
