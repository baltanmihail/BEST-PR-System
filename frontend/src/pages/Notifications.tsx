import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCircle2, Filter, Activity as ActivityIcon } from 'lucide-react'
import { notificationsApi } from '../services/notifications'
import { activityApi, type ActivityItem } from '../services/activity'
import { useThemeStore } from '../store/themeStore'
import { useState } from 'react'

type TabMode = 'notifications' | 'activity'

export default function Notifications() {
  const { theme } = useThemeStore()
  const [tab, setTab] = useState<TabMode>('notifications')
  const [filter, setFilter] = useState<'all' | 'unread' | 'important'>('all')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['notifications', filter],
    queryFn: () => notificationsApi.getNotifications({
      unread_only: filter === 'unread',
      important_only: filter === 'important',
      limit: 50,
    }),
    enabled: tab === 'notifications',
  })

  const { data: activityData, isLoading: activityLoading } = useQuery({
    queryKey: ['activity', 'feed'],
    queryFn: () => activityApi.getFeed({ limit: 50, days: 14 }),
    enabled: tab === 'activity',
  })

  const markAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] })
    },
  })

  const markAllAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
      queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] })
    },
  })

  const importantNotifications = data?.important || []
  const regularRaw = data?.regular || []
  const importantIds = new Set(importantNotifications.map((n) => n.id))
  const regularNotifications = regularRaw.filter((n) => !importantIds.has(n.id))
  const allNotifications = data?.items || []
  const activities = activityData?.items || []

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6">
      <div className={`glass-enhanced ${theme} rounded-xl md:rounded-2xl p-4 md:p-8 mb-6 md:mb-8 text-white`}>
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-4 md:mb-6 gap-4">
          <div className="flex items-center space-x-3">
            <Bell className="h-6 w-6 md:h-8 md:w-8 text-best-primary" />
            <div>
              <h1 className={`text-2xl md:text-3xl font-bold text-white text-readable ${theme}`}>Уведомления</h1>
              {data && tab === 'notifications' && (
                <span className={`inline-block md:ml-3 mt-1 md:mt-0 px-2 md:px-3 py-1 bg-best-primary/20 rounded-full text-xs md:text-sm text-readable ${theme}`}>
                  {data.unread_count} непрочитанных
                </span>
              )}
            </div>
          </div>
          {tab === 'notifications' && (
            <button
              onClick={() => markAllAsReadMutation.mutate()}
              disabled={markAllAsReadMutation.isPending || !data?.unread_count}
              className="px-3 md:px-4 py-2 bg-white/20 rounded-lg hover:bg-white/30 transition-all disabled:opacity-50 text-xs md:text-sm touch-manipulation"
            >
              Отметить все как прочитанные
            </button>
          )}
        </div>

        {/* Tabs: Уведомления / Активность */}
        <div className="flex items-center gap-2 mb-5 border-b border-white/10 pb-3">
          <button
            onClick={() => setTab('notifications')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${
              tab === 'notifications' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/70 hover:bg-white/20'
            }`}
          >
            <Bell className="h-4 w-4" />
            Уведомления
          </button>
          <button
            onClick={() => setTab('activity')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${
              tab === 'activity' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/70 hover:bg-white/20'
            }`}
          >
            <ActivityIcon className="h-4 w-4" />
            Активность
          </button>
        </div>

        {/* Notifications tab */}
        {tab === 'notifications' && (
          <>
            {/* Фильтры */}
            <div className="flex flex-wrap items-center gap-2 mb-6">
              <Filter className="h-5 w-5 text-white/60 hidden md:block" />
              <button
                onClick={() => setFilter('all')}
                className={`px-3 md:px-4 py-2 rounded-lg transition-all text-sm md:text-base touch-manipulation ${
                  filter === 'all' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/80 hover:bg-white/20'
                }`}
              >
                Все
              </button>
              <button
                onClick={() => setFilter('unread')}
                className={`px-3 md:px-4 py-2 rounded-lg transition-all text-sm md:text-base touch-manipulation ${
                  filter === 'unread' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/80 hover:bg-white/20'
                }`}
              >
                Непрочитанные ({data?.unread_count || 0})
              </button>
              <button
                onClick={() => setFilter('important')}
                className={`px-3 md:px-4 py-2 rounded-lg transition-all text-sm md:text-base touch-manipulation ${
                  filter === 'important' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/80 hover:bg-white/20'
                }`}
              >
                Важные ({data?.important_count || 0})
              </button>
            </div>

            {filter === 'all' && importantNotifications.length > 0 && (
              <div className="mb-6">
                <h2 className={`text-xl font-bold text-white mb-4 text-readable ${theme}`}>Важные</h2>
                <div className="space-y-2">
                  {importantNotifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      onMarkAsRead={() => markAsReadMutation.mutate(notification.id)}
                      theme={theme}
                    />
                  ))}
                </div>
              </div>
            )}

            <div>
              {filter === 'all' && importantNotifications.length > 0 && (
                <h2 className={`text-xl font-bold text-white mb-4 text-readable ${theme}`}>Обычные</h2>
              )}
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-best-primary"></div>
                </div>
              ) : (filter === 'all' ? regularNotifications : allNotifications).length === 0 ? (
                <div className="text-center py-12 text-white/60">
                  <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Нет уведомлений</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {(filter === 'all' ? regularNotifications : allNotifications).map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      onMarkAsRead={() => markAsReadMutation.mutate(notification.id)}
                      theme={theme}
                    />
                  ))}
                </div>
              )}
            </div>
          </>
        )}

        {/* Activity tab */}
        {tab === 'activity' && (
          <div>
            {activityLoading ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-best-primary"></div>
              </div>
            ) : activities.length === 0 ? (
              <div className="text-center py-12 text-white/60">
                <ActivityIcon className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Нет активности за последние 14 дней</p>
              </div>
            ) : (
              <div className="space-y-2">
                {activities.map((activity: ActivityItem) => (
                  <div
                    key={activity.id}
                    className="p-4 rounded-lg bg-white/10 border border-white/20 hover:bg-white/15 transition-all"
                  >
                    <div className="flex items-start space-x-3">
                      <div className="flex-shrink-0 w-2 h-2 bg-best-primary rounded-full mt-2" />
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
        )}
      </div>
    </div>
  )
}

function NotificationItem({
  notification,
  onMarkAsRead,
  theme,
}: {
  notification: any
  onMarkAsRead: () => void
  theme: string
}) {
  return (
    <div
      className={`p-4 rounded-lg border ${
        notification.is_read
          ? 'bg-white/5 border-white/10'
          : 'bg-white/10 border-white/30'
      } hover:bg-white/15 transition-all`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className={`font-semibold text-white text-readable ${theme}`}>{notification.title}</h3>
            {notification.is_important && (
              <span className="px-2 py-0.5 bg-red-500/30 rounded text-xs text-red-300">Важно</span>
            )}
            {!notification.is_read && (
              <span className="w-2 h-2 bg-best-primary rounded-full"></span>
            )}
          </div>
          <p className={`text-white/80 text-sm text-readable ${theme}`}>{notification.message}</p>
          <p className={`text-white/50 text-xs mt-2 text-readable ${theme}`}>
            {new Date(notification.created_at).toLocaleString('ru-RU')}
          </p>
        </div>
        {!notification.is_read && (
          <button
            onClick={onMarkAsRead}
            className="ml-4 p-2 hover:bg-white/20 rounded-lg transition-all"
            title="Отметить как прочитанное"
          >
            <CheckCircle2 className="h-5 w-5 text-white/60" />
          </button>
        )}
      </div>
    </div>
  )
}
