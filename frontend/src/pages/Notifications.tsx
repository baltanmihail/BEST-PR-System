import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCircle2, Filter, AlertCircle } from 'lucide-react'
import { notificationsApi } from '../services/notifications'
import { useThemeStore } from '../store/themeStore'
import { useState } from 'react'

export default function Notifications() {
  const { theme } = useThemeStore()
  const [filter, setFilter] = useState<'all' | 'unread' | 'important'>('all')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['notifications', filter],
    queryFn: () => notificationsApi.getNotifications({
      unread_only: filter === 'unread',
      important_only: filter === 'important',
      limit: 50,
    }),
  })

  const markAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const markAllAsReadMutation = useMutation({
    mutationFn: notificationsApi.markAllAsRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const notifications = data?.items || []
  const importantNotifications = data?.important || []
  const regularNotifications = data?.regular || []

  return (
    <div className="max-w-4xl mx-auto">
      <div className={`glass-enhanced ${theme} rounded-2xl p-8 mb-8 text-white`}>
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <Bell className="h-8 w-8 text-best-primary" />
            <h1 className={`text-3xl font-bold text-white text-readable ${theme}`}>Уведомления</h1>
            {data && (
              <span className={`px-3 py-1 bg-best-primary/20 rounded-full text-sm text-readable ${theme}`}>
                {data.unread_count} непрочитанных
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => markAllAsReadMutation.mutate()}
              disabled={markAllAsReadMutation.isPending || !data?.unread_count}
              className="px-4 py-2 bg-white/20 rounded-lg hover:bg-white/30 transition-all disabled:opacity-50 text-sm"
            >
              Отметить все как прочитанные
            </button>
          </div>
        </div>

        {/* Фильтры */}
        <div className="flex items-center space-x-2 mb-6">
          <Filter className="h-5 w-5 text-white/60" />
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'all' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/80 hover:bg-white/20'
            }`}
          >
            Все
          </button>
          <button
            onClick={() => setFilter('unread')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'unread' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/80 hover:bg-white/20'
            }`}
          >
            Непрочитанные ({data?.unread_count || 0})
          </button>
          <button
            onClick={() => setFilter('important')}
            className={`px-4 py-2 rounded-lg transition-all ${
              filter === 'important' ? 'bg-best-primary text-white' : 'bg-white/10 text-white/80 hover:bg-white/20'
            }`}
          >
            Важные ({data?.important_count || 0})
          </button>
        </div>

        {/* Важные уведомления */}
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

        {/* Обычные уведомления */}
        <div>
          {filter === 'all' && importantNotifications.length > 0 && (
            <h2 className={`text-xl font-bold text-white mb-4 text-readable ${theme}`}>Обычные</h2>
          )}
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-best-primary"></div>
            </div>
          ) : notifications.length === 0 ? (
            <div className="text-center py-12 text-white/60">
              <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Нет уведомлений</p>
            </div>
          ) : (
            <div className="space-y-2">
              {notifications.map((notification) => (
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
