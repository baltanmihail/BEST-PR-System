import { create } from 'zustand'

type Theme = 'light' | 'dark'

interface ThemeStore {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeStore>((set) => ({
  theme: (localStorage.getItem('best-pr-theme') as Theme) || 'dark',
  setTheme: (theme) => {
    localStorage.setItem('best-pr-theme', theme)
    set({ theme })
  },
  toggleTheme: () => {
    set((state) => {
      const newTheme = state.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('best-pr-theme', newTheme)
      return { theme: newTheme }
    })
  },
}))
