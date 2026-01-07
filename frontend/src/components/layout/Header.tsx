import { Link } from 'react-router-dom'
import { Sun, Moon } from 'lucide-react'
import { useThemeStore } from '../../store/themeStore'

export default function Header() {
  const { theme, toggleTheme } = useThemeStore()

  return (
    <header className={`glass-enhanced ${theme} border-b border-white/30 sticky top-0 z-50 rounded-none rounded-r-2xl`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center space-x-3 group -ml-2">
            <div className="relative">
              <img 
                src="/BEST_Moscow_white_logo.png" 
                alt="BEST Moscow" 
                className="h-14 object-contain transition-transform group-hover:scale-105"
                onError={(e) => {
                  // Fallback если логотип не загрузился
                  e.currentTarget.style.display = 'none'
                }}
              />
            </div>
          </Link>
          
          <nav className="flex items-center space-x-4">
            <Link
              to="/tasks"
              className="text-white/90 hover:text-white transition-colors font-medium px-3 py-2 rounded-lg hover:bg-white/10"
            >
              Задачи
            </Link>
            <div className="h-6 w-px bg-white/30" />
            <button className="text-white/90 hover:text-white transition-colors font-medium px-3 py-2 rounded-lg hover:bg-white/10">
              Профиль
            </button>
            <div className="h-6 w-px bg-white/30" />
            <button
              onClick={toggleTheme}
              className="text-white/90 hover:text-white transition-colors p-2 rounded-lg hover:bg-white/10 flex items-center justify-center"
              title={theme === 'dark' ? 'Переключить на светлую тему' : 'Переключить на тёмную тему'}
            >
              {theme === 'dark' ? (
                <Sun className="h-5 w-5" />
              ) : (
                <Moon className="h-5 w-5" />
              )}
            </button>
          </nav>
        </div>
      </div>
    </header>
  )
}
