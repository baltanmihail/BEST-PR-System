import { Link, useLocation } from 'react-router-dom'
import { Home, CheckSquare, Trophy, MessageSquare, Bell, Activity, Image, Star, Camera } from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'

const navigation = [
  { name: 'Главная', href: '/', icon: Home },
  { name: 'Задачи', href: '/tasks', icon: CheckSquare },
  { name: 'Рейтинг', href: '/leaderboard', icon: Trophy },
  { name: 'Статистика', href: '/stats', icon: Star },
  { name: 'Оборудование', href: '/equipment', icon: Camera, requiresAuth: true },
  { name: 'Активность', href: '/activity', icon: Activity, requiresAuth: true },
  { name: 'Галерея', href: '/gallery', icon: Image },
  { name: 'Уведомления', href: '/notifications', icon: Bell, requiresAuth: true },
  { name: 'Поддержка', href: '/support', icon: MessageSquare },
]

export default function Sidebar() {
  const location = useLocation()
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const isRegistered = user?.is_active || false

  // Фильтруем навигацию для незарегистрированных пользователей
  const filteredNavigation = navigation.filter(
    item => !item.requiresAuth || isRegistered
  )

  return (
    <aside className={`w-full md:w-64 glass-dark-enhanced ${theme} border-b md:border-b-0 md:border-r border-white/20 md:min-h-[calc(100vh-4rem)]`}>
      <nav className="p-2 md:p-4 flex md:flex-col overflow-x-auto space-x-2 md:space-x-0 md:space-y-2">
        {filteredNavigation.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.href
          
          return (
            <Link
              key={item.name}
              to={item.href}
              className={`
                flex items-center space-x-2 md:space-x-3 px-3 md:px-4 py-2 md:py-3 rounded-lg transition-all card-3d whitespace-nowrap flex-shrink-0
                ${isActive
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/70 hover:text-white hover:bg-white/10'
                }
              `}
            >
              <Icon className="h-4 w-4 md:h-5 md:w-5" />
              <span className="font-medium text-sm md:text-base">{item.name}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
