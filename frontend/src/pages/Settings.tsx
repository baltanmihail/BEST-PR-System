import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings as SettingsIcon, Trash2, AlertTriangle, LogOut, User, Shield, FileText, ArrowLeft, Search, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import api from '../services/api'

export default function Settings() {
  const { theme } = useThemeStore()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [selectedUserForDeletion, setSelectedUserForDeletion] = useState<string | null>(null)
  
  const isVP4PR = user?.role === 'vp4pr'
  
  // Запрос списка пользователей для VP4PR
  const { data: usersData } = useQuery({
    queryKey: ['users', userSearch],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (userSearch) params.append('search', userSearch)
      const response = await api.get(`/auth/users?${params.toString()}`)
      return response.data
    },
    enabled: isVP4PR,
  })

  const deleteAccountMutation = useMutation({
    mutationFn: async (userId: string) => {
      const response = await api.delete(`/auth/account/${userId}`)
      return response.data
    },
    onSuccess: () => {
      // Выходим из системы после удаления аккаунта
      logout()
      navigate('/')
    },
  })

  const handleDeleteAccount = () => {
    const userIdToDelete = selectedUserForDeletion || user?.id
    
    if (!userIdToDelete) return
    
    if (deleteConfirmText !== 'УДАЛИТЬ') {
      alert('Введите "УДАЛИТЬ" для подтверждения')
      return
    }

    deleteAccountMutation.mutate(userIdToDelete)
  }

  if (!user) {
    return (
      <div className="max-w-2xl mx-auto p-4 md:p-6">
        <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8`}>
          <p className="text-white text-center">Необходима авторизация</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center space-x-4 mb-8">
        <Link
          to="/"
          className="p-2 rounded-lg hover:bg-white/10 transition-colors"
        >
          <ArrowLeft className="h-6 w-6 text-white" />
        </Link>
        <div className="flex items-center space-x-3">
          <SettingsIcon className="h-8 w-8 text-best-primary" />
          <h1 className={`text-3xl md:text-4xl font-bold text-readable ${theme}`}>Настройки</h1>
        </div>
      </div>

      {/* Информация о пользователе */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8 space-y-6 mb-6`}>
        <div>
          <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
            Информация об аккаунте
          </h2>
          
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <User className="h-5 w-5 text-best-primary" />
              <div>
                <p className="text-white/60 text-sm">Имя</p>
                <p className={`text-white text-readable ${theme}`}>{user.full_name}</p>
              </div>
            </div>

            {user.username && (
              <div className="flex items-center space-x-3">
                <User className="h-5 w-5 text-best-primary" />
                <div>
                  <p className="text-white/60 text-sm">Username</p>
                  <p className={`text-white text-readable ${theme}`}>@{user.username}</p>
                </div>
              </div>
            )}

            <div className="flex items-center space-x-3">
              <Shield className="h-5 w-5 text-best-primary" />
              <div>
                <p className="text-white/60 text-sm">Роль</p>
                <p className={`text-white text-readable ${theme}`}>
                  {user.role === 'vp4pr' ? 'VP4PR' :
                   user.role === 'coordinator_smm' ? 'Координатор SMM' :
                   user.role === 'coordinator_design' ? 'Координатор Design' :
                   user.role === 'coordinator_channel' ? 'Координатор Channel' :
                   user.role === 'coordinator_prfr' ? 'Координатор PR-FR' :
                   user.role === 'active_participant' ? 'Активный участник' :
                   user.role === 'participant' ? 'Участник' :
                   'Новичок'}
                </p>
              </div>
            </div>

            <div className="flex items-center space-x-3">
              <FileText className="h-5 w-5 text-best-primary" />
              <div>
                <p className="text-white/60 text-sm">Статус</p>
                <p className={`text-white text-readable ${theme}`}>
                  {user.is_active ? '✅ Активен' : '⏳ На модерации'}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Управление пользователями (только для VP4PR) */}
      {isVP4PR && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8 space-y-6 mb-6`}>
          <div>
            <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
              <Users className="h-6 w-6 inline-block mr-2 text-best-primary" />
              Управление пользователями
            </h2>
            
            <div className="mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-white/50" />
                <input
                  type="text"
                  placeholder="Поиск по имени или username..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-best-primary"
                />
              </div>
            </div>

            {usersData?.items && usersData.items.length > 0 && (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {usersData.items.map((u: any) => (
                  <div
                    key={u.id}
                    className="p-3 bg-white/5 rounded-lg border border-white/10 flex items-center justify-between"
                  >
                    <div className="flex-1">
                      <p className="text-white font-medium">{u.full_name}</p>
                      {u.username && (
                        <p className="text-white/60 text-sm">@{u.username}</p>
                      )}
                      <p className="text-white/50 text-xs">
                        {u.role} • {u.points} баллов • {u.is_active ? '✅ Активен' : '⏳ На модерации'}
                      </p>
                    </div>
                    {u.id !== user?.id && (
                      <button
                        onClick={() => setSelectedUserForDeletion(u.id)}
                        className="px-3 py-1 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-all text-sm font-medium"
                      >
                        Удалить
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            {usersData?.items && usersData.items.length === 0 && (
              <p className="text-white/60 text-center py-4">Пользователи не найдены</p>
            )}
          </div>
        </div>
      )}

      {/* Опасная зона */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8 space-y-6 border-2 border-red-500/50`}>
        <div>
          <h2 className={`text-xl font-semibold text-red-400 mb-2 text-readable ${theme}`}>
            ⚠️ Опасная зона
          </h2>
          <p className={`text-white/70 text-sm text-readable ${theme}`}>
            Действия в этой секции необратимы. Будьте осторожны.
          </p>
        </div>

        {!showDeleteConfirm ? (
          <div className="space-y-4">
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
              <div className="flex items-start space-x-3">
                <Trash2 className="h-5 w-5 text-red-400 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-white font-medium mb-1">Удалить аккаунт</h3>
                  <p className="text-white/70 text-sm mb-3">
                    Удаление аккаунта необратимо. Все ваши данные будут удалены, включая задачи, баллы и достижения.
                    Вы не сможете восстановить аккаунт после удаления.
                  </p>
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-all font-medium"
                  >
                    Удалить аккаунт
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="p-4 bg-red-500/20 border-2 border-red-500/50 rounded-lg">
              <div className="flex items-start space-x-3 mb-4">
                <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5" />
                <div className="flex-1">
                  <h3 className="text-white font-medium mb-2">⚠️ Подтверждение удаления</h3>
                  <p className="text-white/80 text-sm mb-4">
                    Это действие необратимо. {selectedUserForDeletion ? 'Все данные пользователя' : 'Все ваши данные'} будут удалены:
                  </p>
                  <ul className="text-white/70 text-sm space-y-1 mb-4 list-disc list-inside">
                    <li>{selectedUserForDeletion ? 'Профиль и персональные данные пользователя' : 'Ваш профиль и персональные данные'}</li>
                    <li>{selectedUserForDeletion ? 'Все задачи и назначения пользователя' : 'Все задачи и назначения'}</li>
                    <li>{selectedUserForDeletion ? 'Баллы и достижения пользователя' : 'Баллы и достижения'}</li>
                    <li>{selectedUserForDeletion ? 'Заявки на оборудование пользователя' : 'Заявки на оборудование'}</li>
                    <li>{selectedUserForDeletion ? 'История активности пользователя' : 'История активности'}</li>
                  </ul>
                  <p className="text-white font-medium mb-2">
                    Для подтверждения введите <span className="text-red-400 font-bold">УДАЛИТЬ</span>:
                  </p>
                  <input
                    type="text"
                    value={deleteConfirmText}
                    onChange={(e) => setDeleteConfirmText(e.target.value)}
                    placeholder="Введите УДАЛИТЬ"
                    className="w-full px-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-red-500 mb-4"
                  />
                  <div className="flex space-x-3">
                    <button
                      onClick={handleDeleteAccount}
                      disabled={deleteAccountMutation.isPending || deleteConfirmText !== 'УДАЛИТЬ'}
                      className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-all font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
                    >
                      <Trash2 className="h-4 w-4" />
                      <span>
                        {deleteAccountMutation.isPending ? 'Удаление...' : 'Подтвердить удаление'}
                      </span>
                    </button>
                    <button
                      onClick={() => {
                        setShowDeleteConfirm(false)
                        setDeleteConfirmText('')
                        setSelectedUserForDeletion(null)
                      }}
                      className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
                    >
                      Отмена
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {deleteAccountMutation.error && (
              <div className="p-4 bg-red-500/20 border border-red-500/50 rounded-lg">
                <p className="text-white text-sm">
                  {(deleteAccountMutation.error as any)?.response?.data?.detail || 
                   'Ошибка при удалении аккаунта. Попробуйте позже.'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Выход из аккаунта */}
      <div className={`mt-6 glass-enhanced ${theme} rounded-xl p-6 md:p-8`}>
        <button
          onClick={() => {
            logout()
            navigate('/')
          }}
          className="w-full px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all font-medium flex items-center justify-center space-x-2"
        >
          <LogOut className="h-4 w-4" />
          <span>Выйти из аккаунта</span>
        </button>
      </div>
    </div>
  )
}
