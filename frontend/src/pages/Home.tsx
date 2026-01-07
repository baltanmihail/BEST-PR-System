import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, ArrowRight, Target, Trophy, Users } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { tasksApi } from '../services/tasks'
import { publicApi } from '../services/public'
import { useAuthStore } from '../store/authStore'
import { useEffect } from 'react'
import { useParallaxHover } from '../hooks/useParallaxHover'
import { useThemeStore } from '../store/themeStore'
import MotivationalChat from '../components/MotivationalChat'

export default function Home() {
  const { fetchUser, user } = useAuthStore()
  const { theme } = useThemeStore()
  const navigate = useNavigate()
  
  // Загружаем пользователя при монтировании
  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  const isCoordinator = user?.role?.includes('coordinator') || user?.role === 'vp4pr'
  const isRegistered = user && user.is_active
  const isUnregistered = !user || !user.is_active

  // Загружаем данные в зависимости от роли
  const { data: tasksData } = useQuery({
    queryKey: ['tasks', 'stats'],
    queryFn: () => tasksApi.getTasks({ limit: 100 }),
    enabled: !!user,
  })

  const { data: publicStats } = useQuery({
    queryKey: ['public', 'stats'],
    queryFn: () => publicApi.getStats(),
    enabled: isUnregistered,
  })

  const activeTasksCount = tasksData?.items?.filter(
    (task) => task.status !== 'completed' && task.status !== 'cancelled'
  ).length || publicStats?.active_tasks || 0

  const heroParallax = useParallaxHover(10) // Главное окно - оставляем как есть
  const card1Parallax = useParallaxHover(15) // Усилил параллакс
  const card2Parallax = useParallaxHover(15) // Усилил параллакс
  const card3Parallax = useParallaxHover(15) // Усилил параллакс

  return (
    <div className="max-w-7xl mx-auto">
      <MotivationalChat />
      
      {/* Hero Section - разный контент для разных ролей */}
      <div 
        ref={heroParallax.ref}
        style={{ transform: heroParallax.transform }}
        className={`glass-enhanced ${theme} rounded-2xl p-8 mb-8 text-white card-3d parallax-hover`}
      >
        <div className="flex items-center space-x-3 mb-4">
          <Sparkles className="h-8 w-8" />
          <h1 className={`text-4xl font-bold text-readable ${theme}`}>
            {isCoordinator
              ? 'Панель координатора'
              : isRegistered
              ? `Добро пожаловать, ${user?.full_name || 'участник'}!`
              : 'Добро пожаловать в BEST PR System!'}
          </h1>
        </div>
        <p className={`text-xl text-white text-readable ${theme} mb-6`}>
          {isCoordinator
            ? 'Управляйте задачами, модерацией и командой'
            : isRegistered
            ? 'Система управления задачами PR-отдела с геймификацией'
            : 'Присоединяйся к команде PR-отдела! Смотри задачи, зарабатывай баллы, развивайся!'}
        </p>
        {isUnregistered && (
          <div className="flex items-center space-x-4">
            <Link
              to="/tasks"
              data-cursor-action="view-tasks"
              className="inline-flex items-center space-x-2 bg-white/20 text-white px-6 py-3 rounded-lg font-semibold hover:bg-white/30 transition-all card-3d border border-white/30"
            >
              <span>Посмотреть задачи</span>
              <ArrowRight className="h-5 w-5" />
            </Link>
            <button
              onClick={() => navigate('/tasks')}
              className="inline-flex items-center space-x-2 bg-best-primary text-white px-6 py-3 rounded-lg font-semibold hover:bg-best-primary/80 transition-all"
            >
              <span>Зарегистрироваться</span>
              <ArrowRight className="h-5 w-5" />
            </button>
          </div>
        )}
        {isRegistered && (
          <Link
            to="/tasks"
            data-cursor-action="view-tasks"
            className="inline-flex items-center space-x-2 bg-white/20 text-white px-6 py-3 rounded-lg font-semibold hover:bg-white/30 transition-all card-3d border border-white/30"
          >
            <span>Посмотреть задачи</span>
            <ArrowRight className="h-5 w-5" />
          </Link>
        )}
      </div>

      {/* Stats Cards - разный контент для разных ролей */}
      <div className={`grid ${isCoordinator ? 'grid-cols-1 md:grid-cols-4' : 'grid-cols-1 md:grid-cols-3'} gap-6 mb-8`}>
        <div 
          ref={card1Parallax.ref}
          style={{ transform: card1Parallax.transform }}
          className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="relative">
              <Target className="h-7 w-7 text-best-primary drop-shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
              <div className="absolute inset-0 h-7 w-7 text-best-primary blur-md opacity-50">
                <Target className="h-full w-full" />
              </div>
            </div>
            <span className={`text-3xl font-bold text-white text-readable ${theme}`}>{activeTasksCount}</span>
          </div>
          <h3 className={`text-white font-medium text-readable ${theme}`}>Активных задач</h3>
        </div>

        <div
          ref={card2Parallax.ref}
          style={{ transform: card2Parallax.transform }}
          data-static-cursor-anchor="user-level"
          onClick={() => navigate('/stats')}
          className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover cursor-pointer hover:scale-105 transition-transform`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="relative">
              <Sparkles className="h-7 w-7 text-best-secondary drop-shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              <div className="absolute inset-0 h-7 w-7 text-best-secondary blur-md opacity-50">
                <Sparkles className="h-full w-full" />
              </div>
            </div>
            <span className={`text-3xl font-bold text-white text-readable ${theme}`}>{user?.level || 1}</span>
          </div>
          <h3 className={`text-white font-medium text-readable ${theme}`}>Уровень</h3>
        </div>

        <div
          ref={card3Parallax.ref}
          style={{ transform: card3Parallax.transform }}
          data-static-cursor-anchor="top"
          className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover cursor-pointer hover:scale-105 transition-transform`}
        >
          <Link
            to="/leaderboard"
            className="block"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="relative">
                <Trophy className="h-8 w-8 text-best-accent drop-shadow-[0_0_8px_rgba(250,204,21,0.6)]" />
                <div className="absolute inset-0 h-8 w-8 text-best-accent blur-md opacity-50">
                  <Trophy className="h-full w-full" />
                </div>
              </div>
              <span className={`text-3xl font-bold text-white text-readable ${theme}`}>#1</span>
            </div>
            <h3 className={`text-white font-medium text-readable ${theme}`}>Топ</h3>
          </Link>
        </div>
        
        {isCoordinator && (
          <div
            className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover cursor-pointer hover:scale-105 transition-transform`}
            onClick={() => navigate('/notifications')}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="relative">
                <Users className="h-7 w-7 text-best-secondary drop-shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
                <div className="absolute inset-0 h-7 w-7 text-best-secondary blur-md opacity-50">
                  <Users className="h-full w-full" />
                </div>
              </div>
              <span className={`text-3xl font-bold text-white text-readable ${theme}`}>
                {publicStats?.participants_count || 0}
              </span>
            </div>
            <h3 className={`text-white font-medium text-readable ${theme}`}>Участников</h3>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div 
        data-quick-actions
        data-cursor-action="quick-actions"
        className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover-strong`}
      >
        <h2 className={`text-2xl font-bold text-white mb-4 text-readable ${theme}`}>Быстрые действия</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Link
            to="/tasks"
            data-cursor-action="all-tasks"
            className="flex items-center justify-between p-4 bg-white/20 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30"
          >
            <span className="font-medium text-white">Посмотреть все задачи</span>
            <ArrowRight className="h-5 w-5 text-white" />
          </Link>
          <button
            data-cursor-action="create-task"
            data-static-cursor-anchor="create-task"
            className="flex items-center justify-between p-4 bg-white/20 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30"
          >
            <span className="font-medium text-white">Создать задачу</span>
            <ArrowRight className="h-5 w-5 text-white" />
          </button>
        </div>
      </div>
    </div>
  )
}
