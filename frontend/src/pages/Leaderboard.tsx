import { useQuery } from '@tanstack/react-query'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { Award, Trophy, Medal, ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { publicApi } from '../services/public'
import { gamificationApi } from '../services/gamification'

export default function Leaderboard() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const isRegistered = user && user.is_active

  // Используем публичный API для всех, защищённый для зарегистрированных
  const { data: leaderboardData, isLoading, error } = useQuery({
    queryKey: ['leaderboard', isRegistered],
    queryFn: async () => {
      if (isRegistered) {
        return gamificationApi.getLeaderboard(50) // Больше пользователей для зарегистрированных
      } else {
        return publicApi.getLeaderboard()
      }
    },
  })

  // Преобразуем данные из API в нужный формат
  const topUsers = leaderboardData?.map((user, index) => ({
    id: index + 1,
    name: user.name,
    username: user.username,
    points: user.points,
    level: user.level,
    position: user.rank || index + 1,
    completed_tasks: user.completed_tasks || 0,
  })) || []

  const getMedalIcon = (position: number) => {
    if (position === 1) return <Trophy className="h-8 w-8 text-yellow-400" />
    if (position === 2) return <Medal className="h-8 w-8 text-gray-300" />
    if (position === 3) return <Medal className="h-8 w-8 text-amber-600" />
    return <Award className="h-6 w-6 text-white/50" />
  }

  const getPositionBg = (position: number) => {
    if (position === 1) return 'bg-yellow-500/20 border-yellow-400/50'
    if (position === 2) return 'bg-gray-400/20 border-gray-300/50'
    if (position === 3) return 'bg-amber-600/20 border-amber-600/50'
    return 'bg-white/5 border-white/20'
  }

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
          <Trophy className="h-8 w-8 text-best-accent" />
          <h1 className={`text-4xl font-bold text-readable ${theme}`}>Топ пользователей</h1>
        </div>
      </div>

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
              <p className="text-white font-semibold text-lg">Ошибка загрузки рейтинга</p>
              <p className="text-white/80 text-sm mt-1">Проверьте подключение к API</p>
            </div>
          </div>
        </div>
      )}

      {/* Список топа */}
      {!isLoading && !error && topUsers.length === 0 && (
        <div className={`glass-enhanced ${theme} rounded-xl p-12 text-center text-white`}>
          <Trophy className="h-12 w-12 text-white mx-auto mb-4" />
          <p className={`text-white text-lg text-readable ${theme}`}>Пока нет данных рейтинга</p>
        </div>
      )}

      {!isLoading && !error && topUsers.length > 0 && (
        <div className="space-y-4">
        {topUsers.map((user) => (
          <div
            key={user.id}
            className={`glass-enhanced ${theme} rounded-xl p-6 flex items-center justify-between transition-all hover:scale-[1.02]`}
          >
            <div className="flex items-center space-x-4 flex-1">
              {/* Позиция */}
              <div className={`flex items-center justify-center w-16 h-16 rounded-full border-2 ${getPositionBg(user.position)}`}>
                {getMedalIcon(user.position)}
              </div>

              {/* Информация о пользователе */}
              <div className="flex-1">
                <div className="flex items-center space-x-3 mb-2">
                  <h3 className={`text-xl font-semibold text-readable ${theme}`}>{user.name}</h3>
                  {user.position <= 3 && (
                    <span className="px-2 py-1 text-xs font-bold bg-best-primary/30 text-white rounded">
                      #{user.position}
                    </span>
                  )}
                </div>
                <div className="flex items-center space-x-4 text-white/70">
                  <span>Уровень {user.level}</span>
                  <span>•</span>
                  <span>{user.points.toLocaleString('ru-RU')} баллов</span>
                </div>
              </div>
            </div>

            {/* Прогресс (опционально) */}
            <div className="hidden md:block w-32">
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-best-primary to-best-secondary rounded-full"
                  style={{ width: `${(user.points / 1250) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
        </div>
      )}

      {/* Подиум (для топ-3) */}
      {!isLoading && !error && topUsers.length >= 3 && (
      <div className="mt-12 grid grid-cols-3 gap-6">
        {/* 2 место */}
        <div className={`glass-enhanced ${theme} rounded-xl p-6 text-center transform translate-y-4`}>
          <div className="mb-4 flex justify-center">
            <Medal className="h-12 w-12 text-gray-300" />
          </div>
          <h3 className={`text-2xl font-bold text-readable ${theme} mb-2`}>
            {topUsers[1]?.name}
          </h3>
          <p className="text-white/70 text-lg">#{topUsers[1]?.position}</p>
          <p className="text-white/50">{topUsers[1]?.points} баллов</p>
        </div>

        {/* 1 место */}
        <div className={`glass-enhanced ${theme} rounded-xl p-6 text-center transform -translate-y-4 border-2 border-yellow-400/50`}>
          <div className="mb-4 flex justify-center">
            <Trophy className="h-16 w-16 text-yellow-400" />
          </div>
          <h3 className={`text-3xl font-bold text-readable ${theme} mb-2`}>
            {topUsers[0]?.name}
          </h3>
          <p className="text-white/70 text-xl">#{topUsers[0]?.position}</p>
          <p className="text-white/50">{topUsers[0]?.points} баллов</p>
        </div>

        {/* 3 место */}
        <div className={`glass-enhanced ${theme} rounded-xl p-6 text-center transform translate-y-6`}>
          <div className="mb-4 flex justify-center">
            <Medal className="h-12 w-12 text-amber-600" />
          </div>
          <h3 className={`text-2xl font-bold text-readable ${theme} mb-2`}>
            {topUsers[2]?.name}
          </h3>
          <p className="text-white/70 text-lg">#{topUsers[2]?.position}</p>
          <p className="text-white/50">{topUsers[2]?.points} баллов</p>
        </div>
      </div>
      )}
    </div>
  )
}
