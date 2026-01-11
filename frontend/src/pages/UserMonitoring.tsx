import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Users, Search, Shield, Ban, Unlock, TrendingUp, Download, Eye, Loader2, AlertCircle, X, CheckCircle2, Clock, ExternalLink } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { usersApi, type UserProfile } from '../services/users'
import { UserRole } from '../types/user'

export default function UserMonitoring() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [selectedUser, setSelectedUser] = useState<UserProfile | null>(null)
  const [showBlockModal, setShowBlockModal] = useState(false)
  const [blockReason, setBlockReason] = useState('')
  const [showPointsModal, setShowPointsModal] = useState(false)
  const [pointsDelta, setPointsDelta] = useState(0)
  const [pointsReason, setPointsReason] = useState('')
  const [showViewModal, setShowViewModal] = useState(false)

  // Проверяем роль (роль приходит как строка из API через Pydantic, например "vp4pr", "coordinator_smm")
  // Pydantic сериализует enum UserRole в его значение (строку), поэтому user.role - это строка, а не enum
  // VP4PR тоже должен иметь доступ к мониторингу пользователей
  // Используем простую проверку, как в Home.tsx и Sidebar.tsx
  let roleValue = ''
  if (typeof user?.role === 'string') {
    roleValue = user.role.toLowerCase().trim()
  } else if (user?.role && typeof user.role === 'object') {
    const roleObj = user.role as any
    if ('value' in roleObj) {
      roleValue = String(roleObj.value).toLowerCase().trim()
    } else {
      roleValue = String(user.role).toLowerCase().trim()
    }
  } else {
    roleValue = String(user?.role || '').toLowerCase().trim()
  }
  
  const isCoordinator = user && (
    roleValue.includes('coordinator') || 
    roleValue === 'vp4pr' || 
    roleValue === UserRole.VP4PR ||
    roleValue === UserRole.COORDINATOR_SMM ||
    roleValue === UserRole.COORDINATOR_DESIGN ||
    roleValue === UserRole.COORDINATOR_CHANNEL ||
    roleValue === UserRole.COORDINATOR_PRFR
  )

  // Отладка для VP4PR
  if (user && (roleValue === 'vp4pr' || roleValue === UserRole.VP4PR)) {
    console.log('[UserMonitoring] VP4PR user detected:', {
      user,
      roleValue,
      userRole: user.role,
      isCoordinator
    })
  }

  if (!isCoordinator) {
    return (
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <div className={`glass-enhanced ${theme} rounded-xl p-6 text-center`}>
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <p className={`text-white text-xl text-readable ${theme}`}>
            Доступ запрещён. Только координаторы могут просматривать эту страницу.
          </p>
        </div>
      </div>
    )
  }

  const { data: usersData, isLoading } = useQuery({
    queryKey: ['users', 'monitoring', search],
    queryFn: () => usersApi.getUsers({ search, limit: 50 }),
  })

  const blockUserMutation = useMutation({
    mutationFn: ({ userId, reason }: { userId: string; reason?: string }) =>
      usersApi.blockUser(userId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowBlockModal(false)
      setSelectedUser(null)
      setBlockReason('')
    },
  })

  const unblockUserMutation = useMutation({
    mutationFn: (userId: string) => usersApi.unblockUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })

  const adjustPointsMutation = useMutation({
    mutationFn: ({ userId, points, reason }: { userId: string; points: number; reason: string }) =>
      usersApi.adjustPoints(userId, points, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowPointsModal(false)
      setSelectedUser(null)
      setPointsDelta(0)
      setPointsReason('')
    },
  })

  const exportUserDataMutation = useMutation({
    mutationFn: (userId: string) => usersApi.exportUserData(userId),
    onSuccess: (blob, userId) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `user_${userId}_export.json`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    },
  })

  const getRoleName = (role: string) => {
    const roleMap: Record<string, string> = {
      vp4pr: 'VP4PR',
      coordinator_smm: 'Координатор SMM',
      coordinator_design: 'Координатор Design',
      coordinator_channel: 'Координатор Channel',
      coordinator_prfr: 'Координатор PR-FR',
      active_participant: 'Активный участник',
      participant: 'Участник',
      novice: 'Новичок',
    }
    return roleMap[role] || role
  }

  const navigate = useNavigate()

  // Загружаем задачи выбранного пользователя
  const { data: userTasks, isLoading: tasksLoading } = useQuery({
    queryKey: ['user-tasks', selectedUser?.id],
    queryFn: () => selectedUser ? usersApi.getUserTasks(selectedUser.id) : null,
    enabled: !!selectedUser && showViewModal,
  })

  const getTaskTypeLabel = (type: string) => {
    const typeMap: Record<string, string> = {
      smm: 'SMM',
      design: 'Дизайн',
      channel: 'Channel',
      prfr: 'PR-FR',
      multitask: 'Многозадачная',
    }
    return typeMap[type] || type
  }

  const getAssignmentStatusLabel = (status: string) => {
    const statusMap: Record<string, string> = {
      assigned: 'Назначена',
      in_progress: 'В работе',
      completed: 'Завершена',
      cancelled: 'Отменена',
    }
    return statusMap[status] || status
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center space-x-4 mb-8" data-tour="users-header">
        <Link
          to="/"
          className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        >
          <Users className="h-6 w-6 text-white" />
        </Link>
        <div className="flex items-center space-x-3">
          <Shield className="h-8 w-8 text-best-primary" />
          <h1 className={`text-3xl md:text-4xl font-bold text-readable ${theme}`}>
            Мониторинг пользователей
          </h1>
        </div>
      </div>

      {/* Поиск */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6`} data-tour="users-search">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-white/50" />
          <input
            type="text"
            placeholder="Поиск по имени или username..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`w-full pl-10 pr-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
          />
        </div>
      </div>

      {/* Список пользователей */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-tour="users-actions">
          {usersData?.items.map((u: UserProfile) => (
            <div
              key={u.id}
              className={`glass-enhanced ${theme} rounded-xl p-6 card-3d hover:scale-105 transition-transform`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  {u.avatar_url ? (
                    <img
                      src={u.avatar_url}
                      alt={u.full_name}
                      className="w-12 h-12 rounded-full object-cover border-2 border-best-primary"
                    />
                  ) : (
                    <div className="w-12 h-12 rounded-full bg-best-primary/20 flex items-center justify-center">
                      <Users className="h-6 w-6 text-best-primary" />
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <h3 
                      className={`text-white font-semibold text-readable ${theme} break-words`}
                      title={u.full_name}
                    >
                      {u.full_name}
                    </h3>
                    {u.username && (
                      <p className="text-white/60 text-sm truncate" title={`@${u.username}`}>@{u.username}</p>
                    )}
                  </div>
                </div>
                <span
                  className={`px-2 py-1 rounded-full text-xs font-medium ${
                    u.is_active
                      ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                      : 'bg-red-500/20 text-red-400 border border-red-500/50'
                  }`}
                >
                  {u.is_active ? 'Активен' : 'Заблокирован'}
                </span>
              </div>

              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-white/60">Роль:</span>
                  <span className={`text-white text-readable ${theme}`}>{getRoleName(u.role)}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-white/60">Баллы:</span>
                  <span className={`text-white text-readable ${theme}`}>{u.points}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-white/60">Уровень:</span>
                  <span className={`text-white text-readable ${theme}`}>{u.level}</span>
                </div>
                {u.last_activity_at && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-white/60">Активность:</span>
                    <span className={`text-white text-readable ${theme}`}>
                      {new Date(u.last_activity_at).toLocaleDateString('ru-RU')}
                    </span>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => {
                    setSelectedUser(u)
                    setShowViewModal(true)
                  }}
                  className="flex-1 px-3 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all text-sm flex items-center justify-center space-x-1"
                >
                  <Eye className="h-4 w-4" />
                  <span>Просмотр</span>
                </button>
                {u.is_active ? (
                  <button
                    onClick={() => {
                      setSelectedUser(u)
                      setShowBlockModal(true)
                    }}
                    className="px-3 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-all text-sm flex items-center space-x-1"
                  >
                    <Ban className="h-4 w-4" />
                    <span>Заблокировать</span>
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      unblockUserMutation.mutate(u.id)
                    }}
                    className="px-3 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-all text-sm flex items-center space-x-1"
                  >
                    <Unlock className="h-4 w-4" />
                    <span>Разблокировать</span>
                  </button>
                )}
                <button
                  onClick={() => {
                    setSelectedUser(u)
                    setShowPointsModal(true)
                  }}
                  className="px-3 py-2 bg-best-primary/20 text-best-primary rounded-lg hover:bg-best-primary/30 transition-all text-sm flex items-center space-x-1"
                >
                  <TrendingUp className="h-4 w-4" />
                  <span>Баллы</span>
                </button>
                {(roleValue === 'vp4pr' || (typeof user?.role === 'object' && (user.role as any)?.value === UserRole.VP4PR)) && (
                  <button
                    onClick={() => {
                      exportUserDataMutation.mutate(u.id)
                    }}
                    className="px-3 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-all text-sm flex items-center space-x-1"
                    title="Экспорт данных"
                  >
                    <Download className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Модальное окно блокировки */}
      {showBlockModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className={`glass-enhanced ${theme} rounded-xl p-6 max-w-md w-full mx-4`}>
            <h3 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
              Заблокировать пользователя
            </h3>
            <p className={`text-white/70 mb-4 text-readable ${theme}`}>
              {selectedUser.full_name}
            </p>
            <div className="mb-4">
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Причина блокировки (опционально)
              </label>
              <textarea
                value={blockReason}
                onChange={(e) => setBlockReason(e.target.value)}
                rows={3}
                className={`w-full bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary resize-none text-readable ${theme}`}
              />
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  blockUserMutation.mutate({
                    userId: selectedUser.id,
                    reason: blockReason || undefined,
                  })
                }}
                disabled={blockUserMutation.isPending}
                className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-all disabled:opacity-50"
              >
                {blockUserMutation.isPending ? 'Блокировка...' : 'Заблокировать'}
              </button>
              <button
                onClick={() => {
                  setShowBlockModal(false)
                  setSelectedUser(null)
                  setBlockReason('')
                }}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно изменения баллов */}
      {showPointsModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className={`glass-enhanced ${theme} rounded-xl p-6 max-w-md w-full mx-4`}>
            <h3 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
              Изменить баллы
            </h3>
            <p className={`text-white/70 mb-4 text-readable ${theme}`}>
              {selectedUser.full_name} (текущие баллы: {selectedUser.points})
            </p>
            <div className="mb-4">
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Изменение баллов (положительное или отрицательное)
              </label>
              <input
                type="number"
                value={pointsDelta}
                onChange={(e) => setPointsDelta(parseInt(e.target.value) || 0)}
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>
            <div className="mb-4">
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Причина *
              </label>
              <input
                type="text"
                value={pointsReason}
                onChange={(e) => setPointsReason(e.target.value)}
                required
                placeholder="Например: Бонус за выполнение задачи"
                className={`w-full bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  adjustPointsMutation.mutate({
                    userId: selectedUser.id,
                    points: pointsDelta,
                    reason: pointsReason,
                  })
                }}
                disabled={adjustPointsMutation.isPending || !pointsReason}
                className="flex-1 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50"
              >
                {adjustPointsMutation.isPending ? 'Сохранение...' : 'Сохранить'}
              </button>
              <button
                onClick={() => {
                  setShowPointsModal(false)
                  setSelectedUser(null)
                  setPointsDelta(0)
                  setPointsReason('')
                }}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
              >
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно просмотра пользователя */}
      {showViewModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowViewModal(false)}>
          <div 
            className={`glass-enhanced ${theme} rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className={`text-2xl font-semibold text-white text-readable ${theme}`}>
                Профиль пользователя
              </h3>
              <button
                onClick={() => {
                  setShowViewModal(false)
                  setSelectedUser(null)
                }}
                className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                aria-label="Закрыть"
              >
                <X className="h-5 w-5 text-white" />
              </button>
            </div>

            <div className="space-y-6">
              {/* Основная информация */}
              <div className="flex items-start space-x-4">
                {selectedUser.avatar_url ? (
                  <img
                    src={selectedUser.avatar_url}
                    alt={selectedUser.full_name}
                    className="w-20 h-20 rounded-full object-cover border-2 border-best-primary flex-shrink-0"
                  />
                ) : (
                  <div className="w-20 h-20 rounded-full bg-best-primary/20 flex items-center justify-center flex-shrink-0">
                    <Users className="h-10 w-10 text-best-primary" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <h4 className={`text-xl font-bold text-white mb-1 text-readable ${theme} break-words`}>
                    {selectedUser.full_name}
                  </h4>
                  {selectedUser.username && (
                    <p className="text-white/60 text-sm">@{selectedUser.username}</p>
                  )}
                  {selectedUser.telegram_username && selectedUser.telegram_username !== selectedUser.username && (
                    <p className="text-white/60 text-sm">Telegram: @{selectedUser.telegram_username}</p>
                  )}
                  <span
                    className={`inline-block mt-2 px-3 py-1 rounded-full text-xs font-medium ${
                      selectedUser.is_active
                        ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                        : 'bg-red-500/20 text-red-400 border border-red-500/50'
                    }`}
                  >
                    {selectedUser.is_active ? 'Активен' : 'Заблокирован'}
                  </span>
                </div>
              </div>

              {/* Детали */}
              <div className={`bg-white/5 rounded-lg p-4 space-y-3`}>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-white/60 text-sm">Роль:</span>
                    <p className={`text-white font-medium text-readable ${theme}`}>{getRoleName(selectedUser.role)}</p>
                  </div>
                  <div>
                    <span className="text-white/60 text-sm">Telegram ID:</span>
                    <p className={`text-white font-mono text-sm text-readable ${theme}`}>{selectedUser.telegram_id}</p>
                  </div>
                  <div>
                    <span className="text-white/60 text-sm">Баллы:</span>
                    <p className={`text-white font-medium text-readable ${theme}`}>{selectedUser.points}</p>
                  </div>
                  <div>
                    <span className="text-white/60 text-sm">Уровень:</span>
                    <p className={`text-white font-medium text-readable ${theme}`}>{selectedUser.level}</p>
                  </div>
                  <div>
                    <span className="text-white/60 text-sm">Дней подряд:</span>
                    <p className={`text-white font-medium text-readable ${theme}`}>{selectedUser.streak_days}</p>
                  </div>
                  {selectedUser.email && (
                    <div>
                      <span className="text-white/60 text-sm">Email:</span>
                      <p className={`text-white text-sm break-words text-readable ${theme}`}>{selectedUser.email}</p>
                    </div>
                  )}
                  {selectedUser.last_activity_at && (
                    <div>
                      <span className="text-white/60 text-sm">Последняя активность:</span>
                      <p className={`text-white text-sm text-readable ${theme}`}>
                        {new Date(selectedUser.last_activity_at).toLocaleString('ru-RU')}
                      </p>
                    </div>
                  )}
                  <div>
                    <span className="text-white/60 text-sm">Зарегистрирован:</span>
                    <p className={`text-white text-sm text-readable ${theme}`}>
                      {new Date(selectedUser.created_at).toLocaleDateString('ru-RU')}
                    </p>
                  </div>
                </div>

                {selectedUser.bio && (
                  <div>
                    <span className="text-white/60 text-sm block mb-1">О себе:</span>
                    <p className={`text-white text-sm text-readable ${theme} break-words`}>{selectedUser.bio}</p>
                  </div>
                )}

                {selectedUser.contacts && (
                  <div>
                    <span className="text-white/60 text-sm block mb-2">Контакты:</span>
                    <div className="space-y-1">
                      {selectedUser.contacts.phone && (
                        <p className={`text-white text-sm text-readable ${theme}`}>📞 {selectedUser.contacts.phone}</p>
                      )}
                      {selectedUser.contacts.telegram && (
                        <p className={`text-white text-sm text-readable ${theme}`}>✈️ {selectedUser.contacts.telegram}</p>
                      )}
                      {selectedUser.contacts.vk && (
                        <p className={`text-white text-sm text-readable ${theme}`}>🔵 {selectedUser.contacts.vk}</p>
                      )}
                      {selectedUser.contacts.instagram && (
                        <p className={`text-white text-sm text-readable ${theme}`}>📷 {selectedUser.contacts.instagram}</p>
                      )}
                    </div>
                  </div>
                )}

                {selectedUser.skills && selectedUser.skills.length > 0 && (
                  <div>
                    <span className="text-white/60 text-sm block mb-2">Навыки:</span>
                    <div className="flex flex-wrap gap-2">
                      {selectedUser.skills.map((skill, index) => (
                        <span
                          key={index}
                          className="px-2 py-1 bg-best-primary/20 text-best-primary rounded text-xs"
                        >
                          {skill}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Задачи пользователя */}
              <div className="space-y-4">
                <h4 className={`text-lg font-semibold text-white text-readable ${theme}`}>
                  Задачи пользователя
                </h4>
                
                {tasksLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-best-primary" />
                  </div>
                ) : userTasks && userTasks.total > 0 ? (
                  <div className="space-y-4">
                    {/* Активные задачи */}
                    {userTasks.active.length > 0 && (
                      <div>
                        <div className="flex items-center space-x-2 mb-3">
                          <Clock className="h-5 w-5 text-yellow-400" />
                          <h5 className={`text-md font-medium text-white text-readable ${theme}`}>
                            Текущие задачи ({userTasks.active.length})
                          </h5>
                        </div>
                        <div className="space-y-2">
                          {userTasks.active.map(({ task, assignment }) => (
                            <div
                              key={assignment.id}
                              className="bg-white/5 rounded-lg p-4 border border-white/10 hover:border-best-primary/50 transition-colors cursor-pointer"
                              onClick={() => {
                                navigate(`/tasks`)
                                setShowViewModal(false)
                              }}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <h6 className={`text-white font-medium text-readable ${theme} flex-1`}>
                                  {task.title}
                                </h6>
                                <ExternalLink className="h-4 w-4 text-white/40 ml-2 flex-shrink-0" />
                              </div>
                              <div className="flex flex-wrap gap-2 text-xs">
                                <span className="px-2 py-1 bg-best-primary/20 text-best-primary rounded">
                                  {getTaskTypeLabel(task.type)}
                                </span>
                                <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded">
                                  {getAssignmentStatusLabel(assignment.status)}
                                </span>
                                {task.due_date && (
                                  <span className="px-2 py-1 bg-white/10 text-white/70 rounded">
                                    {new Date(task.due_date).toLocaleDateString('ru-RU')}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Выполненные задачи */}
                    {userTasks.completed.length > 0 && (
                      <div>
                        <div className="flex items-center space-x-2 mb-3">
                          <CheckCircle2 className="h-5 w-5 text-green-400" />
                          <h5 className={`text-md font-medium text-white text-readable ${theme}`}>
                            Выполненные задачи ({userTasks.completed.length})
                          </h5>
                        </div>
                        <div className="space-y-2">
                          {userTasks.completed.map(({ task, assignment }) => (
                            <div
                              key={assignment.id}
                              className="bg-white/5 rounded-lg p-4 border border-white/10 hover:border-best-primary/50 transition-colors cursor-pointer"
                              onClick={() => {
                                navigate(`/tasks`)
                                setShowViewModal(false)
                              }}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <h6 className={`text-white font-medium text-readable ${theme} flex-1`}>
                                  {task.title}
                                </h6>
                                <ExternalLink className="h-4 w-4 text-white/40 ml-2 flex-shrink-0" />
                              </div>
                              <div className="flex flex-wrap gap-2 text-xs">
                                <span className="px-2 py-1 bg-best-primary/20 text-best-primary rounded">
                                  {getTaskTypeLabel(task.type)}
                                </span>
                                <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded">
                                  Завершена
                                </span>
                                {assignment.completed_at && (
                                  <span className="px-2 py-1 bg-white/10 text-white/70 rounded">
                                    {new Date(assignment.completed_at).toLocaleDateString('ru-RU')}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-white/60">
                    <p className="text-sm">У пользователя пока нет задач</p>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => {
                  setShowViewModal(false)
                  setSelectedUser(null)
                }}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
