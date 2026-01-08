import { Link, useNavigate } from 'react-router-dom'
import { Sparkles, ArrowRight, Target, Trophy, Users, MessageSquare } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { tasksApi } from '../services/tasks'
import { publicApi } from '../services/public'
import { useAuthStore } from '../store/authStore'
import { useEffect } from 'react'
import { useParallaxHover } from '../hooks/useParallaxHover'
import { useThemeStore } from '../store/themeStore'
import ChatWidget from '../components/ChatWidget'
import { useTour } from '../hooks/useTour'
import { telegramChatsApi, GeneralChatResponse } from '../services/telegramChats'
import { onboardingApi } from '../services/onboarding'

export default function Home() {
  const { fetchUser, user } = useAuthStore()
  const { theme } = useThemeStore()
  const navigate = useNavigate()
  
  // Загружаем пользователя при монтировании
  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  // Инициализируем визит для незарегистрированных пользователей и обрабатываем параметры URL
  useEffect(() => {
    const initVisitForUnregistered = async () => {
      // Получаем telegram_id из URL параметров или localStorage
      const urlParams = new URLSearchParams(window.location.search)
      const telegramId = urlParams.get('telegram_id') || localStorage.getItem('telegram_id')
      const registered = urlParams.get('registered') === 'true'
      const loggedIn = urlParams.get('logged_in') === 'true'
      const approved = urlParams.get('approved') === 'true'
      
      // Очищаем URL параметры после обработки
      if (telegramId || registered || loggedIn || approved) {
        const newUrl = window.location.pathname
        window.history.replaceState({}, '', newUrl)
      }
      
      // Если пользователь не зарегистрирован и есть telegram_id, инициализируем визит
      if ((!user || !user.is_active) && telegramId) {
        try {
          await onboardingApi.initVisit(telegramId)
          // Сохраняем telegram_id для будущих визитов
          if (!localStorage.getItem('telegram_id')) {
            localStorage.setItem('telegram_id', telegramId)
          }
        } catch (error) {
          console.error('Failed to init visit:', error)
        }
      }
      
      // Если пользователь только что зарегистрировался, показываем информацию
      if (registered && (!user || !user.is_active)) {
        // После регистрации показываем информацию о том, что заявка на рассмотрении
        // Обновляем данные пользователя для проверки статуса
        fetchUser()
      }
      
      // Если пользователь только что вошёл или заявка одобрена, обновляем данные и показываем приветствие
      if (loggedIn || approved) {
        // Сначала проверяем, есть ли access_token в localStorage (после QR-подтверждения)
        const accessToken = localStorage.getItem('access_token')
        if (accessToken) {
          // Токен уже есть - просто обновляем данные пользователя
          fetchUser().then(() => {
            // После обновления данных показываем приветственное сообщение
            // Это уже обрабатывается в компоненте через user.is_active
          })
        } else {
          // Токена нет - возможно, пользователь пришёл с бота без QR
          // В этом случае fetchUser всё равно попытается загрузить пользователя по токену из localStorage
          // Если токена нет, fetchUser просто ничего не сделает (пользователь не авторизован)
          fetchUser()
        }
      }
    }

    initVisitForUnregistered()
  }, [user, fetchUser])

  const isCoordinator = user?.role?.includes('coordinator') || user?.role === 'vp4pr'
  const isRegistered = !!(user && user.is_active)
  const isUnregistered = !user || !user.is_active
  
  // Хук для тура (используется в Layout)
  const { } = useTour()
  
  // Получаем информацию об общем чате
  const { data: generalChat } = useQuery<GeneralChatResponse, Error>({
    queryKey: ['general-chat'],
    queryFn: telegramChatsApi.getGeneralChat,
    enabled: isRegistered === true,
  })

  // Загружаем данные в зависимости от роли
  const { data: tasksData } = useQuery({
    queryKey: ['tasks', 'stats', isRegistered],
    queryFn: async () => {
      if (isRegistered) {
        return tasksApi.getTasks({ limit: 50 })
      } else {
        const publicTasksResponse = await publicApi.getTasks({ limit: 50 })
        return {
          items: publicTasksResponse.items.map(task => ({
            id: task.id,
            title: task.title,
            type: task.type,
            status: 'open',
            priority: task.priority || 'medium',
            due_date_relative: task.due_date_relative,
            participants_count: task.participants_count,
            stages_count: task.stages_count,
          })),
          total: publicTasksResponse.total,
          skip: publicTasksResponse.skip,
          limit: publicTasksResponse.limit
        }
      }
    },
    enabled: isUnregistered || !!user, // Загружаем для всех
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
      <ChatWidget />
      
      {/* Hero Section - разный контент для разных ролей */}
      <div 
        ref={heroParallax.ref}
        style={{ transform: heroParallax.transform }}
        data-tour="hero"
        className={`glass-enhanced ${theme} rounded-xl md:rounded-2xl p-4 md:p-8 mb-6 md:mb-8 text-white card-3d parallax-hover`}
      >
        <div className="flex items-center space-x-2 md:space-x-3 mb-3 md:mb-4">
          <Sparkles className="h-6 w-6 md:h-8 md:w-8 flex-shrink-0" />
          <h1 className={`text-2xl md:text-4xl font-bold text-readable ${theme}`}>
            {isCoordinator
              ? 'Панель координатора'
              : isRegistered
              ? `Добро пожаловать, ${user?.full_name || 'участник'}!`
              : 'Добро пожаловать в BEST PR System!'}
          </h1>
        </div>
        <p className={`text-base md:text-xl text-white text-readable ${theme} mb-4 md:mb-6`}>
          {isCoordinator
            ? 'Управляйте задачами, модерацией и командой'
            : isRegistered
            ? 'Система управления задачами PR-отдела с геймификацией'
            : 'Присоединяйся к команде PR-отдела! Смотри задачи, зарабатывай баллы, развивайся!'}
        </p>
        {isUnregistered && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
            <Link
              to="/tasks"
              data-tour="tasks-link"
              data-cursor-action="view-tasks"
              className="inline-flex items-center justify-center space-x-2 bg-white/20 text-white px-4 md:px-6 py-2.5 md:py-3 rounded-lg font-semibold hover:bg-white/30 transition-all card-3d border border-white/30 text-sm md:text-base"
            >
              <span>Посмотреть задачи</span>
              <ArrowRight className="h-4 w-4 md:h-5 md:w-5" />
            </Link>
            <Link
              to="/register"
              className="inline-flex items-center justify-center space-x-2 bg-best-primary text-white px-4 md:px-6 py-2.5 md:py-3 rounded-lg font-semibold hover:bg-best-primary/80 transition-all text-sm md:text-base"
            >
              <span>Зарегистрироваться</span>
              <ArrowRight className="h-4 w-4 md:h-5 md:w-5" />
            </Link>
          </div>
        )}
        {isRegistered && (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 sm:gap-4">
            <Link
              to="/tasks"
              data-tour="tasks-link"
              data-cursor-action="view-tasks"
              className="inline-flex items-center justify-center space-x-2 bg-white/20 text-white px-4 md:px-6 py-2.5 md:py-3 rounded-lg font-semibold hover:bg-white/30 transition-all card-3d border border-white/30 text-sm md:text-base"
            >
              <span>Посмотреть задачи</span>
              <ArrowRight className="h-4 w-4 md:h-5 md:w-5" />
            </Link>
            {generalChat?.exists && generalChat.invite_link && (
              <a
                href={generalChat.invite_link}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center space-x-2 bg-best-primary text-white px-4 md:px-6 py-2.5 md:py-3 rounded-lg font-semibold hover:bg-best-primary/80 transition-all text-sm md:text-base"
              >
                <MessageSquare className="h-4 w-4 md:h-5 md:w-5" />
                <span>Общий чат</span>
              </a>
            )}
          </div>
        )}
      </div>

      {/* Stats Cards - разный контент для разных ролей */}
      <div className={`grid ${isCoordinator ? 'grid-cols-1 sm:grid-cols-2 md:grid-cols-4' : 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3'} gap-4 md:gap-6 mb-6 md:mb-8`}>
        <div 
          ref={card1Parallax.ref}
          style={{ transform: card1Parallax.transform }}
          className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover`}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="relative">
              <Target className="h-7 w-7 text-best-primary drop-shadow-[0_0_5px_rgba(59,130,246,0.4)]" />
              <div className="absolute inset-0 h-7 w-7 text-best-primary blur-md opacity-40 translate-y-0.5">
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
          className={`glass-enhanced ${theme} rounded-xl p-4 md:p-6 card-3d text-white parallax-hover cursor-pointer hover:scale-105 transition-transform`}
        >
          <div className="flex items-center justify-between mb-3 md:mb-4">
            <div className="relative">
              <Sparkles className="h-6 w-6 md:h-7 md:w-7 text-best-secondary drop-shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
              <div className="absolute inset-0 h-6 w-6 md:h-7 md:w-7 text-best-secondary blur-md opacity-50">
                <Sparkles className="h-full w-full" />
              </div>
            </div>
            <span className={`text-2xl md:text-3xl font-bold text-white text-readable ${theme}`}>{user?.level || 1}</span>
          </div>
          <h3 className={`text-white font-medium text-sm md:text-base text-readable ${theme}`}>Уровень</h3>
        </div>

        <div
          ref={card3Parallax.ref}
          style={{ transform: card3Parallax.transform }}
          data-static-cursor-anchor="top"
          className={`glass-enhanced ${theme} rounded-xl p-4 md:p-6 card-3d text-white parallax-hover cursor-pointer hover:scale-105 transition-transform`}
        >
          <Link
            to="/leaderboard"
            data-tour="leaderboard-link"
            className="block"
          >
            <div className="flex items-center justify-between mb-3 md:mb-4">
              <div className="relative">
                <Trophy className="h-7 w-7 md:h-8 md:w-8 text-best-accent drop-shadow-[0_0_8px_rgba(250,204,21,0.6)]" />
                <div className="absolute inset-0 h-7 w-7 md:h-8 md:w-8 text-best-accent blur-md opacity-50">
                  <Trophy className="h-full w-full" />
                </div>
              </div>
              <span className={`text-2xl md:text-3xl font-bold text-white text-readable ${theme}`}>#1</span>
            </div>
            <h3 className={`text-white font-medium text-sm md:text-base text-readable ${theme}`}>Топ</h3>
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
        <div className={`grid ${isCoordinator ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'} gap-4`}>
          <Link
            to="/tasks"
            data-cursor-action="all-tasks"
            className="flex items-center justify-between p-4 bg-white/20 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30"
          >
            <span className="font-medium text-white">Посмотреть все задачи</span>
            <ArrowRight className="h-5 w-5 text-white" />
          </Link>
          {isRegistered && generalChat?.exists && generalChat.invite_link && (
            <a
              href={generalChat.invite_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-between p-4 bg-white/20 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30"
            >
              <span className="font-medium text-white">💬 Общий чат команды</span>
              <MessageSquare className="h-5 w-5 text-white" />
            </a>
          )}
          {isCoordinator && (
            <button
              data-cursor-action="create-task"
              data-static-cursor-anchor="create-task"
              onClick={() => {
                // TODO: Добавить страницу создания задачи или модальное окно
                alert('Функция создания задачи будет доступна в ближайшее время')
              }}
              className="flex items-center justify-between p-4 bg-white/20 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30"
            >
              <span className="font-medium text-white">Создать задачу</span>
              <ArrowRight className="h-5 w-5 text-white" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
