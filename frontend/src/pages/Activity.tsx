import { useQuery } from '@tanstack/react-query'
import { Activity as ActivityIcon, Loader2 } from 'lucide-react'
import { activityApi } from '../services/activity'
import { useThemeStore } from '../store/themeStore'

export default function Activity() {
  const { theme } = useThemeStore()

  const { data, isLoading } = useQuery({
    queryKey: ['activity', 'feed'],
    queryFn: () => activityApi.getFeed({ limit: 50, days: 7 }),
  })

  const activities = data?.items || []

  return (
    <div className="max-w-4xl mx-auto">
      <div className={`glass-enhanced ${theme} rounded-2xl p-8 mb-8 text-white`}>
        <div className="flex items-center space-x-3 mb-6">
          <ActivityIcon className="h-8 w-8 text-best-primary" />
          <h1 className={`text-3xl font-bold text-white text-readable ${theme}`}>Лента активности</h1>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
          </div>
        ) : activities.length === 0 ? (
          <div className="text-center py-12 text-white/60">
            <ActivityIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Нет активности за последние 7 дней</p>
          </div>
        ) : (
          <div className="space-y-4">
            {activities.map((activity) => (
              <div
                key={activity.id}
                className={`p-4 rounded-lg bg-white/10 border border-white/20 hover:bg-white/15 transition-all`}
              >
                <div className="flex items-start space-x-3">
                  <div className="flex-shrink-0 w-2 h-2 bg-best-primary rounded-full mt-2"></div>
                  <div className="flex-1">
                    <p className={`text-white text-readable ${theme}`}>{activity.message}</p>
                    {activity.user_name && (
                      <p className={`text-white/60 text-sm mt-1 text-readable ${theme}`}>
                        {activity.user_name}
                      </p>
                    )}
                    <p className={`text-white/40 text-xs mt-2 text-readable ${theme}`}>
                      {new Date(activity.timestamp).toLocaleString('ru-RU')}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
