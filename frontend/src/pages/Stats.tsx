import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { Sparkles, Trophy, Award, TrendingUp, Target, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useEffect } from 'react'

export default function Stats() {
  const { fetchUser, user } = useAuthStore()
  const { theme } = useThemeStore()

  useEffect(() => {
    fetchUser()
  }, [fetchUser])

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
          <Sparkles className="h-8 w-8 text-best-secondary" />
          <h1 className={`text-4xl font-bold text-readable ${theme}`}>Ваша статистика</h1>
        </div>
      </div>

      <div className="space-y-6">
        {/* Уровень */}
        <div className={`glass-enhanced ${theme} rounded-xl p-8`}>
          <div className="flex items-center space-x-3 mb-6">
            <TrendingUp className="h-8 w-8 text-best-secondary" />
            <h2 className={`text-2xl font-semibold text-readable ${theme}`}>Уровень</h2>
          </div>
          <div className="flex items-baseline space-x-3 mb-6">
            <span className={`text-5xl font-bold text-readable ${theme}`}>{user?.level || 1}</span>
            <span className="text-white/70 text-xl">уровень</span>
          </div>
          {/* Прогресс до следующего уровня */}
          <div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden mb-2">
              <div 
                className="h-full bg-gradient-to-r from-best-primary to-best-secondary rounded-full transition-all"
                style={{ width: '65%' }}
              />
            </div>
            <p className="text-white/60 text-sm">До следующего уровня: 350 баллов</p>
          </div>
        </div>

        {/* Баллы */}
        <div className={`glass-enhanced ${theme} rounded-xl p-8`}>
          <div className="flex items-center space-x-3 mb-6">
            <Trophy className="h-8 w-8 text-best-accent" />
            <h2 className={`text-2xl font-semibold text-readable ${theme}`}>Баллы</h2>
          </div>
          <div className="flex items-baseline space-x-3 mb-4">
            <span className={`text-5xl font-bold text-readable ${theme}`}>{user?.points || 0}</span>
            <span className="text-white/70 text-xl">баллов</span>
          </div>
          <p className="text-white/60">Всего заработано баллов за всё время</p>
        </div>

        {/* Достижения */}
        <div className={`glass-enhanced ${theme} rounded-xl p-8`}>
          <div className="flex items-center space-x-3 mb-6">
            <Award className="h-8 w-8 text-best-primary" />
            <h2 className={`text-2xl font-semibold text-readable ${theme}`}>Достижения</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {/* Примеры достижений */}
            <div className="text-center">
              <div className="w-20 h-20 mx-auto mb-3 bg-best-primary/20 rounded-full flex items-center justify-center">
                <Trophy className="h-10 w-10 text-best-accent" />
              </div>
              <p className="text-white/90 font-medium">Первая задача</p>
              <p className="text-white/50 text-sm mt-1">Выполнена</p>
            </div>
            <div className="text-center">
              <div className="w-20 h-20 mx-auto mb-3 bg-best-primary/20 rounded-full flex items-center justify-center">
                <Sparkles className="h-10 w-10 text-best-secondary" />
              </div>
              <p className="text-white/90 font-medium">Уровень 5</p>
              <p className="text-white/50 text-sm mt-1">Достигнут</p>
            </div>
            <div className="text-center">
              <div className="w-20 h-20 mx-auto mb-3 bg-best-primary/20 rounded-full flex items-center justify-center">
                <Target className="h-10 w-10 text-best-primary" />
              </div>
              <p className="text-white/90 font-medium">10 задач</p>
              <p className="text-white/50 text-sm mt-1">Достигнуто</p>
            </div>
            <div className="text-center">
              <div className="w-20 h-20 mx-auto mb-3 bg-white/10 rounded-full flex items-center justify-center">
                <Award className="h-10 w-10 text-white/30" />
              </div>
              <p className="text-white/40 font-medium">Заблокировано</p>
              <p className="text-white/30 text-sm mt-1">Недоступно</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
