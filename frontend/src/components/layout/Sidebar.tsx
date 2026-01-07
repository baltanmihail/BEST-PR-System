import { Link, useLocation } from 'react-router-dom'
import { Home, CheckSquare, Trophy, MessageSquare, Bell, Activity, Image } from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'

const navigation = [
  { name: 'Главная', href: '/', icon: Home },
  { name: 'Задачи', href: '/tasks', icon: CheckSquare },
  { name: 'Рейтинг', href: '/leaderboard', icon: Trophy },
  { name: 'Статистика', href: '/stats', icon: Trophy },
  { name: 'Активность', href: '/activity', icon: Activity },
  { name: 'Галерея', href: '/gallery', icon: Image },
  { name: 'Уведомления', href: '/notifications', icon: Bell },
  { name: 'Поддержка', href: '/support', icon: MessageSquare },
]

export default function Sidebar() {
  const location = useLocation()
  const { theme } = useThemeStore()

  return (
    <aside className={`w-64 glass-dark-enhanced ${theme} border-r border-white/20 min-h-[calc(100vh-4rem)]`}>
      <nav className="p-4 space-y-2">
        {navigation.map((item) => {
          const Icon = item.icon
          const isActive = location.pathname === item.href
          
          return (
            <Link
              key={item.name}
              to={item.href}
              className={`
                flex items-center space-x-3 px-4 py-3 rounded-lg transition-all card-3d
                ${isActive
                  ? 'bg-white/20 text-white shadow-lg'
                  : 'text-white/70 hover:text-white hover:bg-white/10'
                }
              `}
            >
              <Icon className="h-5 w-5" />
              <span className="font-medium">{item.name}</span>
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
