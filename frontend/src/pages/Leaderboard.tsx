import { useThemeStore } from '../store/themeStore'
import { Award, Trophy, Medal, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

export default function Leaderboard() {
  const { theme } = useThemeStore()

  // Заглушка данных топа - позже подключить к API
  const topUsers = [
    { id: 1, name: 'Иван Петров', points: 1250, level: 8, position: 1 },
    { id: 2, name: 'Мария Смирнова', points: 1180, level: 7, position: 2 },
    { id: 3, name: 'Алексей Иванов', points: 1120, level: 7, position: 3 },
    { id: 4, name: 'Елена Козлова', points: 980, level: 6, position: 4 },
    { id: 5, name: 'Дмитрий Новиков', points: 920, level: 6, position: 5 },
    { id: 6, name: 'Анна Федорова', points: 850, level: 5, position: 6 },
    { id: 7, name: 'Сергей Волков', points: 780, level: 5, position: 7 },
    { id: 8, name: 'Ольга Морозова', points: 720, level: 5, position: 8 },
    { id: 9, name: 'Павел Лебедев', points: 650, level: 4, position: 9 },
    { id: 10, name: 'Татьяна Соколова', points: 580, level: 4, position: 10 },
  ]

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

      {/* Список топа */}
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

      {/* Подиум (для топ-3) */}
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
    </div>
  )
}
