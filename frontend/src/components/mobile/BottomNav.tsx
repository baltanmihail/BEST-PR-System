import { Home, Calendar, PlusSquare, Image, User } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'

interface BottomNavProps {
  onTabChange?: (tab: string) => void
  activeTab?: string
}

export default function BottomNav({ onTabChange, activeTab = 'home' }: BottomNavProps) {
  const navigate = useNavigate()
  // const location = useLocation() // В будущем можно привязать к роутингу

  const navItems = [
    { id: 'home', icon: Home, label: 'Главная' },
    { id: 'calendar', icon: Calendar, label: 'Задачи' },
    { id: 'create', icon: PlusSquare, label: 'Создать', isPrimary: true },
    { id: 'gallery', icon: Image, label: 'Галерея' },
    { id: 'profile', icon: User, label: 'Профиль' },
  ]

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 px-4 pb-4 pt-2">
      <div className="bg-[#1a1a2e]/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl flex justify-around items-center py-3 px-2">
        {navItems.map((item) => {
          const isActive = activeTab === item.id
          const Icon = item.icon
          
          if (item.isPrimary) {
            return (
              <button
                key={item.id}
                onClick={() => onTabChange?.(item.id)}
                className="relative -mt-8 bg-best-primary text-white p-4 rounded-full shadow-lg shadow-best-primary/40 transform transition-transform active:scale-95"
              >
                <Icon className="h-6 w-6" />
              </button>
            )
          }

          return (
            <button
              key={item.id}
              onClick={() => onTabChange?.(item.id)}
              className={`flex flex-col items-center gap-1 transition-colors ${
                isActive ? 'text-best-primary' : 'text-white/40 hover:text-white/70'
              }`}
            >
              <Icon className={`h-6 w-6 ${isActive ? 'stroke-[2.5px]' : 'stroke-[1.5px]'}`} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}