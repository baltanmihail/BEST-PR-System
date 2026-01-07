import { ReactNode, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import Background3DModels from '../Background3DModels'
import StaticCursor3D from '../StaticCursor3D'
import Cursor2 from '../Cursor2'
import { useThemeStore } from '../../store/themeStore'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const mainRef = useRef<HTMLElement>(null)
  const { theme } = useThemeStore()
  const location = useLocation()

  useEffect(() => {
    let wheelTimeoutId: number
    let lastWheelTime = 0
    let wheelVelocity = 0

    const handleWheel = (e: WheelEvent) => {
      const now = Date.now()
      const deltaTime = now - lastWheelTime
      lastWheelTime = now

      // Вычисляем скорость вращения колёсика
      const delta = Math.abs(e.deltaY)
      if (deltaTime > 0) {
        wheelVelocity = delta / deltaTime * 1000
      }

      // Убираем эффект размытия - он мешает читать контент
    }

    window.addEventListener('wheel', handleWheel, { passive: true })
    return () => {
      window.removeEventListener('wheel', handleWheel)
      clearTimeout(wheelTimeoutId)
    }
  }, [])

  return (
    <div className={`min-h-screen bg-gradient-best ${theme} relative overflow-hidden`}>
      {/* 3D модели логотипов BEST - парят и плавно двигаются */}
      <div className="fixed inset-0 pointer-events-none z-[1]" style={{ backdropFilter: 'blur(0px)' }}>
        <Background3DModels />
      </div>
      
      {/* Декоративные градиентные круги - как в примере */}
      <div className="absolute top-0 left-0 w-[600px] h-[600px] bg-best-secondary/10 rounded-full blur-3xl -translate-x-1/3 -translate-y-1/3 animate-pulse"></div>
      <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-best-accent/8 rounded-full blur-3xl translate-x-1/3 translate-y-1/3 animate-pulse" style={{ animationDelay: '1s' }}></div>
      <div className="absolute top-1/2 left-1/2 w-[700px] h-[700px] bg-best-primary/12 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2 animate-pulse" style={{ animationDelay: '2s' }}></div>
      <div className="absolute bottom-1/4 left-1/4 w-[400px] h-[400px] bg-best-accent/6 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '0.5s' }}></div>
      
      {/* Статичная 3D модель курсора */}
      <StaticCursor3D />
      {/* Cursor-2: кастомный курсор пользователя (пока только Home) */}
      <Cursor2 />
      
      <Header />
      <div className="flex relative z-10">
        <Sidebar />
        <main 
          ref={mainRef}
          className="flex-1 p-6 relative z-10 glass-trail"
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
    </div>
  )
}
