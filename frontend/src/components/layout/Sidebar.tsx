import { Link, useLocation } from 'react-router-dom'
import { Home, CheckSquare, Trophy, MessageSquare, Bell, Activity, Image, Star, Camera, Settings, Shield, Calendar, X } from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'
import { useAuthStore } from '../../store/authStore'
import { UserRole } from '../../types/user'
import { useEffect } from 'react'

const navigation = [
  { name: 'Главная', href: '/', icon: Home },
  { name: 'Задачи', href: '/tasks', icon: CheckSquare },
  { name: 'Календарь', href: '/calendar', icon: Calendar },
  { name: 'Рейтинг', href: '/leaderboard', icon: Trophy },
  { name: 'Статистика', href: '/stats', icon: Star },
  { name: 'Оборудование', href: '/equipment', icon: Camera, requiresAuth: true },
  { name: 'Активность', href: '/activity', icon: Activity, requiresAuth: true },
  { name: 'Галерея', href: '/gallery', icon: Image },
  { name: 'Уведомления', href: '/notifications', icon: Bell, requiresAuth: true },
  { name: 'Поддержка', href: '/support', icon: MessageSquare },
  { name: 'Настройки', href: '/settings', icon: Settings, requiresAuth: true },
  { name: 'Мониторинг', href: '/users', icon: Shield, requiresCoordinator: true },
]

interface SidebarProps {
  isOpen?: boolean
  onClose?: () => void
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const location = useLocation()
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const isRegistered = user?.is_active || false
  
  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  // Фильтруем навигацию для незарегистрированных пользователей и координаторов
  const filteredNavigation = navigation.filter(
    item => {
      if (item.requiresCoordinator) {
        return isCoordinator
      }
      return !item.requiresAuth || isRegistered
    }
  )

  // Закрываем меню при переходе на другую страницу (только на мобильных)
  useEffect(() => {
    if (isOpen && onClose && window.innerWidth < 768) {
      onClose()
    }
  }, [location.pathname, isOpen, onClose])

  return (
    <>
      {/* Overlay для мобильных */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={onClose}
        />
      )}
      
      {/* Sidebar */}
      <aside className={`
        fixed md:static inset-y-0 left-0 z-50 md:z-auto
        w-64 md:w-64
        glass-dark-enhanced ${theme}
        border-r border-white/20
        transform transition-transform duration-300 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        md:min-h-[calc(100vh-4rem)]
      `}>
        {/* Кнопка закрытия для мобильных */}
        {isOpen && onClose && (
          <div className="flex items-center justify-between p-4 border-b border-white/20 md:hidden">
            <h2 className="text-white font-semibold text-lg">Меню</h2>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              aria-label="Закрыть меню"
            >
              <X className="h-5 w-5 text-white" />
            </button>
          </div>
        )}
        
        <nav className="p-2 md:p-4 flex flex-col overflow-y-auto h-full md:h-auto">
          {filteredNavigation.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.href
            
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={onClose} // Закрываем меню при клике на мобильных
                data-tour={item.href === '/support' ? 'support-link' : undefined}
                className={`
                  flex items-center space-x-3 px-4 py-3 rounded-lg transition-all card-3d
                  ${isActive
                    ? 'bg-white/20 text-white shadow-lg'
                    : 'text-white/70 hover:text-white hover:bg-white/10'
                  }
                `}
              >
                <Icon className="h-5 w-5 flex-shrink-0" />
                <span className="font-medium text-base">{item.name}</span>
              </Link>
            )
          })}
        </nav>
      </aside>
    </>
  )
}
