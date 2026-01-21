import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/layout/Layout'
import Home from './pages/Home'
import Tasks from './pages/Tasks'
import CreateTask from './pages/CreateTask'
import Stats from './pages/Stats'
import Leaderboard from './pages/Leaderboard'
import Support from './pages/Support'
import Notifications from './pages/Notifications'
import Activity from './pages/Activity'
import Gallery from './pages/Gallery'
import Register from './pages/Register'
import Login from './pages/Login'
import Equipment from './pages/Equipment'
import Settings from './pages/Settings'
import UserMonitoring from './pages/UserMonitoring'
import Calendar from './pages/Calendar'
import Timeline from './pages/Timeline'
import { useAuthStore } from './store/authStore'
import { useThemeStore } from './store/themeStore'
import { authApi } from './services/auth'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

// Компонент для проверки Telegram WebApp и автоматического входа
function AppContent() {
  const { user, login, fetchUser } = useAuthStore()
  const { theme } = useThemeStore()
  const navigate = useNavigate()
  const location = useLocation()

  // Инициализация Telegram WebApp
  useEffect(() => {
    const tg = window.Telegram?.WebApp
    if (tg) {
      // Инициализируем WebApp
      tg.ready()
      
      // Расширяем на весь экран
      tg.expand()
      
      // Настраиваем тему в зависимости от темы приложения
      if (theme === 'dark') {
        tg.setHeaderColor('#1a1a2e') // Тёмный цвет для хедера
        tg.setBackgroundColor('#0f0f1e') // Тёмный цвет для фона
      } else {
        tg.setHeaderColor('#ffffff') // Светлый цвет для хедера
        tg.setBackgroundColor('#f5f5f5') // Светлый цвет для фона
      }
      
      // Используем viewportHeight для адаптации на мобильных
      if (tg.viewportHeight) {
        document.documentElement.style.setProperty('--tg-viewport-height', `${tg.viewportHeight}px`)
      }
      
      console.log('Telegram WebApp initialized', {
        version: tg.version,
        platform: tg.platform,
        colorScheme: tg.colorScheme,
        viewportHeight: tg.viewportHeight,
        theme,
      })
    }
  }, [theme])

  useEffect(() => {
    // Проверяем, есть ли токен в URL (после регистрации через QR)
    const urlParams = new URLSearchParams(window.location.search)
    const tokenFromUrl = urlParams.get('token')
    const registered = urlParams.get('registered') === 'true'
    
    if (tokenFromUrl && registered && !user) {
      // Сохраняем токен и авторизуем пользователя
      localStorage.setItem('access_token', tokenFromUrl)
      login(tokenFromUrl)
      
      // Удаляем token из URL для безопасности
      urlParams.delete('token')
      const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '')
      window.history.replaceState({}, '', newUrl)
      
      // Редирект на главную
      if (location.pathname === '/login') {
        navigate('/')
      }
      return
    }
    
    // Проверяем, открыт ли сайт через Telegram WebApp
    const isTelegramWebApp = window.Telegram?.WebApp
    
    if (isTelegramWebApp && !user && window.Telegram) {
      const tg = window.Telegram.WebApp
      const initDataUnsafe = tg.initDataUnsafe
      
      // Если есть данные пользователя из Telegram WebApp
      if (initDataUnsafe?.user?.id) {
        const telegramId = initDataUnsafe.user.id
        
        // Пытаемся автоматически войти через бота (для зарегистрированных пользователей)
        authApi.botLogin(telegramId)
          .then((response) => {
            // Успешный вход
            login(response.access_token)
            // Если мы на странице входа, перенаправляем на главную
            if (location.pathname === '/login') {
              navigate('/')
            }
          })
          .catch((error) => {
            // Пользователь не зарегистрирован или неактивен
            // Оставляем на текущей странице (Login покажет QR-код)
            console.log('Bot login failed (user not registered or inactive):', error)
          })
      }
    } else if (!user) {
      // Если не в Telegram WebApp, проверяем сохранённый токен
      fetchUser()
    }
  }, []) // Выполняется только при монтировании

  return (
    <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/tasks/create" element={<CreateTask />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/support" element={<Support />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/activity" element={<Activity />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/register" element={<Register />} />
            <Route path="/login" element={<Login />} />
            <Route path="/equipment" element={<Equipment />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/users" element={<UserMonitoring />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/timeline" element={<Timeline />} />
          </Routes>
        </Layout>
  )
}

export default App
