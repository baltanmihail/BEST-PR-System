import { ReactNode, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import Background3DModels from '../Background3DModels'
import StaticCursor3D from '../StaticCursor3D'
import Cursor2 from '../Cursor2'
import TourGuide from '../TourGuide'
import ChatWidget from '../ChatWidget'
import { useThemeStore } from '../../store/themeStore'
import { useTour } from '../../hooks/useTour'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const mainRef = useRef<HTMLElement>(null)
  const { theme } = useThemeStore()
  const location = useLocation()
  const { steps, isActive, completeTour, stopTour } = useTour()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  useEffect(() => {
    const handleWheel = (_e: WheelEvent) => {
      // Убираем эффект размытия - он мешает читать контент
      // Обработчик оставлен для возможного будущего использования
    }

    window.addEventListener('wheel', handleWheel, { passive: true })
    return () => {
      window.removeEventListener('wheel', handleWheel)
    }
  }, [])

  // Определяем, мобильное ли устройство для оптимизации
  const [isMobile, setIsMobile] = useState(false)
  
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768 || 'ontouchstart' in window)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  return (
    <div className={`min-h-screen bg-gradient-best ${theme} relative overflow-hidden`}>
      {/* 3D модели логотипов BEST - парят и плавно двигаются (отключены на мобильных для производительности) */}
      {!isMobile && (
        <div className="fixed inset-0 pointer-events-none z-[1]" style={{ backdropFilter: 'blur(0px)' }}>
          <Background3DModels />
        </div>
      )}
      
      {/* Декоративные градиентные круги - как в примере */}
      <div className="absolute top-0 left-0 w-[600px] h-[600px] bg-best-secondary/10 rounded-full blur-3xl -translate-x-1/3 -translate-y-1/3 animate-pulse"></div>
      <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-best-accent/8 rounded-full blur-3xl translate-x-1/3 translate-y-1/3 animate-pulse" style={{ animationDelay: '1s' }}></div>
      <div className="absolute top-1/2 left-1/2 w-[700px] h-[700px] bg-best-primary/12 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2 animate-pulse" style={{ animationDelay: '2s' }}></div>
      <div className="absolute bottom-1/4 left-1/4 w-[400px] h-[400px] bg-best-accent/6 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '0.5s' }}></div>
      
      {/* Статичная 3D модель курсора (отключена на мобильных) */}
      {!isMobile && <StaticCursor3D />}
      {/* Cursor-2: кастомный курсор пользователя (отключен на мобильных) */}
      {!isMobile && <Cursor2 />}
      
      <Header onMenuToggle={() => setIsMobileMenuOpen(!isMobileMenuOpen)} />
      <div className="flex flex-col md:flex-row relative z-10">
        <Sidebar isOpen={isMobileMenuOpen} onClose={() => setIsMobileMenuOpen(false)} />
        <main 
          ref={mainRef}
          className="flex-1 p-4 md:p-6 relative z-10 glass-trail"
          style={{
            transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), filter 0.2s ease-out',
            backdropFilter: 'blur(3px)', // Размытие фона (3D моделей) при наложении
            WebkitBackdropFilter: 'blur(3px)',
          }}
        >
          <div key={location.pathname} className="page-fade-in">
            {children}
          </div>
        </main>
      </div>
      
      {/* Гайд - работает на всех страницах */}
      {isActive && steps.length > 0 && (
        <TourGuide
          steps={steps}
          onComplete={completeTour}
          onSkip={stopTour}
          showSkip={true}
        />
      )}
      
      {/* Чат виджет - доступен на всех страницах */}
      <ChatWidget />
    </div>
  )
}
