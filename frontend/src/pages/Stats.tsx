import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { Trophy, Award, TrendingUp, ArrowLeft, Star, Loader2, AlertCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { gamificationApi } from '../services/gamification'

export default function Stats() {
  const { fetchUser, user } = useAuthStore()
  const { theme } = useThemeStore()

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

  const isRegistered = user && user.is_active

  // Загружаем статистику пользователя
  const { data: userStats, isLoading, error } = useQuery({
    queryKey: ['gamification', 'stats'],
    queryFn: () => gamificationApi.getMyStats(),
    enabled: !!isRegistered,
  })

  // Загружаем достижения
  const { data: achievements } = useQuery({
    queryKey: ['gamification', 'achievements'],
    queryFn: () => gamificationApi.getMyAchievements(),
    enabled: !!isRegistered,
  })

  const currentLevel = userStats?.level || user?.level || 1
  const currentPoints = userStats?.points || user?.points || 0
  const nextLevelPoints = userStats?.next_level_points || 1000
  const currentLevelPoints = userStats?.current_level_points || 0
  const progressPercent = nextLevelPoints > 0 
    ? Math.min((currentLevelPoints / (nextLevelPoints - currentLevelPoints)) * 100, 100)
    : 0
  const pointsToNext = nextLevelPoints - currentLevelPoints

  return (
    <div className="max-w-5xl mx-auto">
      {/* Заголовок */}
      <div className="flex items-center space-x-4 mb-8">
        <Link
          to="/"
          className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        >
          <ArrowLeft className="h-6 w-6 text-white" />
        </Link>
        <div className="flex items-center space-x-3">
          <Star className="h-8 w-8 text-best-secondary" />
          <h1 className={`text-4xl font-bold text-readable ${theme}`}>Ваша статистика</h1>
        </div>
      </div>

      {/* Предупреждение для незарегистрированных */}
      {!isRegistered && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6 border-2 border-yellow-500/50 bg-yellow-500/10`}>
          <div className="flex items-center space-x-3">
            <AlertCircle className="h-6 w-6 text-yellow-400" />
            <div>
              <p className={`text-white font-semibold text-readable ${theme}`}>
                Для просмотра статистики необходимо зарегистрироваться
              </p>
              <Link
                to="/register"
                className="text-best-primary hover:text-best-primary/80 underline mt-1 inline-block"
              >
                Перейти к регистрации →
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Загрузка */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
        </div>
      )}

      {/* Ошибка */}
      {error && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 border-2 border-status-red/50 bg-red-500/20 backdrop-blur-xl mb-6`}>
          <div className="flex items-center space-x-3">
            <AlertCircle className="h-6 w-6 text-white flex-shrink-0" />
            <div>
              <p className="text-white font-semibold text-lg">Ошибка загрузки статистики</p>
              <p className="text-white/80 text-sm mt-1">Проверьте подключение к API</p>
            </div>
          </div>
        </div>
      )}

      {!isLoading && !error && isRegistered && (
        <div className="space-y-6">
          {/* Уровень */}
          <div className={`glass-enhanced ${theme} rounded-xl p-8`}>
            <div className="flex items-center space-x-3 mb-6">
              <TrendingUp className="h-8 w-8 text-best-secondary" />
              <h2 className={`text-2xl font-semibold text-readable ${theme}`}>Уровень</h2>
            </div>
            <div className="flex items-baseline space-x-3 mb-6">
              <span className={`text-5xl font-bold text-readable ${theme}`}>{currentLevel}</span>
              <span className="text-white/70 text-xl">уровень</span>
            </div>
            {/* Прогресс до следующего уровня */}
            <div>
              <div className="h-3 bg-white/10 rounded-full overflow-hidden mb-2">
                <div 
                  className="h-full bg-gradient-to-r from-best-primary to-best-secondary rounded-full transition-all"
                  style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
                />
              </div>
              <p className="text-white/60 text-sm">
                До следующего уровня: {pointsToNext > 0 ? pointsToNext : 0} баллов
              </p>
            </div>
          </div>

          {/* Баллы */}
          <div className={`glass-enhanced ${theme} rounded-xl p-8`}>
            <div className="flex items-center space-x-3 mb-6">
              <Trophy className="h-8 w-8 text-best-accent" />
              <h2 className={`text-2xl font-semibold text-readable ${theme}`}>Баллы</h2>
            </div>
            <div className="flex items-baseline space-x-3 mb-4">
              <span className={`text-5xl font-bold text-readable ${theme}`}>{currentPoints}</span>
              <span className="text-white/70 text-xl">баллов</span>
            </div>
            <p className="text-white/60">Всего заработано баллов за всё время</p>
            {userStats && (
              <div className="mt-4 space-y-2 text-white/60 text-sm">
                <p>Выполнено задач: {userStats.completed_tasks || 0}</p>
                <p>Всего задач: {userStats.total_tasks || 0}</p>
                <p>Серия дней: {userStats.streak_days || 0}</p>
              </div>
            )}
          </div>

          {/* Достижения */}
          <div className={`glass-enhanced ${theme} rounded-xl p-8`}>
            <div className="flex items-center space-x-3 mb-6">
              <Award className="h-8 w-8 text-best-primary" />
              <h2 className={`text-2xl font-semibold text-readable ${theme}`}>Достижения</h2>
            </div>
            {achievements && achievements.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                {achievements.map((achievement) => (
                  <div key={achievement.id} className="text-center">
                    <div className="w-20 h-20 mx-auto mb-3 bg-best-primary/20 rounded-full flex items-center justify-center">
                      <Award className="h-10 w-10 text-best-primary" />
                    </div>
                    <p className="text-white/90 font-medium">{achievement.name}</p>
                    <p className="text-white/50 text-sm mt-1">
                      {new Date(achievement.unlocked_at).toLocaleDateString('ru-RU')}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Award className="h-16 w-16 text-white/30 mx-auto mb-4" />
                <p className="text-white/60">Пока нет достижений</p>
                <p className="text-white/40 text-sm mt-2">Выполняй задачи, чтобы зарабатывать достижения!</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
