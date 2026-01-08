import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Settings as SettingsIcon, Trash2, AlertTriangle, LogOut, User, Shield, FileText, ArrowLeft, Search, Users, Edit, Save, X, Plus, Camera, Mail, Phone, MessageCircle, Globe, Instagram } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import api from '../services/api'
import { usersApi, type ProfileUpdate } from '../services/users'

export default function Settings() {
  const { theme } = useThemeStore()
  const { user, logout, fetchUser } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [userSearch, setUserSearch] = useState('')
  const [selectedUserForDeletion, setSelectedUserForDeletion] = useState<string | null>(null)
  const [isEditingProfile, setIsEditingProfile] = useState(false)
  const [profileData, setProfileData] = useState<ProfileUpdate>({
    full_name: user?.full_name || '',
    bio: user?.bio || '',
    contacts: user?.contacts || {},
    skills: user?.skills || [],
    portfolio: user?.portfolio || [],
  })
  const [newSkill, setNewSkill] = useState('')
  const [newPortfolioItem, setNewPortfolioItem] = useState({
    title: '',
    description: '',
    url: '',
    type: 'link' as 'photo' | 'video' | 'link',
  })
  
  const isVP4PR = user?.role === 'vp4pr'
  
  // Загружаем полный профиль
  const { data: fullProfile } = useQuery({
    queryKey: ['user', 'profile', user?.id],
    queryFn: () => usersApi.getMyProfile(),
    enabled: !!user,
  })

  const updateProfileMutation = useMutation({
    mutationFn: (data: ProfileUpdate) => usersApi.updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] })
      fetchUser()
      setIsEditingProfile(false)
    },
  })

  const uploadPhotoMutation = useMutation({
    mutationFn: (file: File) => usersApi.uploadPhoto(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] })
      fetchUser()
    },
  })
  
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

      {/* Редактирование профиля */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8 space-y-6 mb-6`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className={`text-xl font-semibold text-white text-readable ${theme}`}>
            Мой профиль
          </h2>
          {!isEditingProfile && (
            <button
              onClick={() => {
                setProfileData({
                  full_name: fullProfile?.full_name || user?.full_name || '',
                  bio: fullProfile?.bio || '',
                  contacts: fullProfile?.contacts || {},
                  skills: fullProfile?.skills || [],
                  portfolio: fullProfile?.portfolio || [],
                })
                setIsEditingProfile(true)
              }}
              className="flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all"
            >
              <Edit className="h-4 w-4" />
              <span>Редактировать</span>
            </button>
          )}
        </div>

        {isEditingProfile ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              updateProfileMutation.mutate(profileData)
            }}
            className="space-y-6"
          >
            {/* Фото профиля */}
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Фото профиля
              </label>
              <div className="flex items-center space-x-4">
                {fullProfile?.avatar_url && (
                  <img
                    src={fullProfile.avatar_url}
                    alt="Avatar"
                    className="w-20 h-20 rounded-full object-cover border-2 border-best-primary"
                  />
                )}
                <label className="flex items-center space-x-2 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all cursor-pointer">
                  <Camera className="h-4 w-4" />
                  <span>Загрузить фото</span>
                  <input
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) {
                        uploadPhotoMutation.mutate(file)
                      }
                    }}
                  />
                </label>
              </div>
            </div>

            {/* Имя */}
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Имя *
              </label>
              <input
                type="text"
                value={profileData.full_name}
                onChange={(e) => setProfileData({ ...profileData, full_name: e.target.value })}
                required
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>

            {/* Био */}
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                О себе
              </label>
              <textarea
                value={profileData.bio || ''}
                onChange={(e) => setProfileData({ ...profileData, bio: e.target.value })}
                rows={4}
                placeholder="Расскажите о себе..."
                className={`w-full bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary resize-none text-readable ${theme}`}
              />
            </div>

            {/* Контакты */}
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Контакты
              </label>
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Mail className="h-4 w-4 text-white/60" />
                  <input
                    type="email"
                    value={profileData.contacts?.email || ''}
                    onChange={(e) => setProfileData({
                      ...profileData,
                      contacts: { ...profileData.contacts, email: e.target.value }
                    })}
                    placeholder="Email"
                    className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Phone className="h-4 w-4 text-white/60" />
                  <input
                    type="tel"
                    value={profileData.contacts?.phone || ''}
                    onChange={(e) => setProfileData({
                      ...profileData,
                      contacts: { ...profileData.contacts, phone: e.target.value }
                    })}
                    placeholder="Телефон"
                    className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <MessageCircle className="h-4 w-4 text-white/60" />
                  <input
                    type="text"
                    value={profileData.contacts?.telegram || ''}
                    onChange={(e) => setProfileData({
                      ...profileData,
                      contacts: { ...profileData.contacts, telegram: e.target.value }
                    })}
                    placeholder="@telegram"
                    className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Globe className="h-4 w-4 text-white/60" />
                  <input
                    type="text"
                    value={profileData.contacts?.vk || ''}
                    onChange={(e) => setProfileData({
                      ...profileData,
                      contacts: { ...profileData.contacts, vk: e.target.value }
                    })}
                    placeholder="VK"
                    className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Instagram className="h-4 w-4 text-white/60" />
                  <input
                    type="text"
                    value={profileData.contacts?.instagram || ''}
                    onChange={(e) => setProfileData({
                      ...profileData,
                      contacts: { ...profileData.contacts, instagram: e.target.value }
                    })}
                    placeholder="@instagram"
                    className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  />
                </div>
              </div>
            </div>

            {/* Навыки */}
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Навыки
              </label>
              <div className="flex flex-wrap gap-2 mb-3">
                {profileData.skills?.map((skill, index) => (
                  <span
                    key={index}
                    className="px-3 py-1 bg-best-primary/20 text-best-primary rounded-full text-sm flex items-center space-x-2"
                  >
                    <span>{skill}</span>
                    <button
                      type="button"
                      onClick={() => {
                        const newSkills = profileData.skills?.filter((_, i) => i !== index) || []
                        setProfileData({ ...profileData, skills: newSkills })
                      }}
                      className="text-best-primary hover:text-red-400"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={newSkill}
                  onChange={(e) => setNewSkill(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      if (newSkill.trim()) {
                        setProfileData({
                          ...profileData,
                          skills: [...(profileData.skills || []), newSkill.trim()]
                        })
                        setNewSkill('')
                      }
                    }
                  }}
                  placeholder="Добавить навык"
                  className={`flex-1 bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                />
                <button
                  type="button"
                  onClick={() => {
                    if (newSkill.trim()) {
                      setProfileData({
                        ...profileData,
                        skills: [...(profileData.skills || []), newSkill.trim()]
                      })
                      setNewSkill('')
                    }
                  }}
                  className="px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Кнопки */}
            <div className="flex space-x-3">
              <button
                type="submit"
                disabled={updateProfileMutation.isPending}
                className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                <span>{updateProfileMutation.isPending ? 'Сохранение...' : 'Сохранить'}</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsEditingProfile(false)
                  setProfileData({
                    full_name: fullProfile?.full_name || user?.full_name || '',
                    bio: fullProfile?.bio || '',
                    contacts: fullProfile?.contacts || {},
                    skills: fullProfile?.skills || [],
                    portfolio: fullProfile?.portfolio || [],
                  })
                }}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            {/* Информация о пользователе */}
            <div>
              <h3 className={`text-lg font-semibold text-white mb-4 text-readable ${theme}`}>
                Информация об аккаунте
              </h3>
          
              <div className="space-y-4">
            {fullProfile?.avatar_url && (
              <div className="flex items-center space-x-3 mb-4">
                <img
                  src={fullProfile.avatar_url}
                  alt="Avatar"
                  className="w-16 h-16 rounded-full object-cover border-2 border-best-primary"
                />
              </div>
            )}
            <div className="flex items-center space-x-3">
              <User className="h-5 w-5 text-best-primary" />
              <div>
                <p className="text-white/60 text-sm">Имя</p>
                <p className={`text-white text-readable ${theme}`}>{fullProfile?.full_name || user.full_name}</p>
              </div>
            </div>
            {fullProfile?.bio && (
              <div>
                <p className="text-white/60 text-sm mb-1">О себе</p>
                <p className={`text-white text-readable ${theme}`}>{fullProfile.bio}</p>
              </div>
            )}
            {(fullProfile?.contacts?.email || fullProfile?.contacts?.phone || fullProfile?.contacts?.telegram || fullProfile?.contacts?.vk || fullProfile?.contacts?.instagram) && (
              <div>
                <p className="text-white/60 text-sm mb-2">Контакты</p>
                <div className="space-y-1">
                  {fullProfile.contacts?.email && (
                    <p className={`text-white text-readable ${theme}`}>📧 {fullProfile.contacts.email}</p>
                  )}
                  {fullProfile.contacts?.phone && (
                    <p className={`text-white text-readable ${theme}`}>📱 {fullProfile.contacts.phone}</p>
                  )}
                  {fullProfile.contacts?.telegram && (
                    <p className={`text-white text-readable ${theme}`}>💬 {fullProfile.contacts.telegram}</p>
                  )}
                  {fullProfile.contacts?.vk && (
                    <p className={`text-white text-readable ${theme}`}>🌐 {fullProfile.contacts.vk}</p>
                  )}
                  {fullProfile.contacts?.instagram && (
                    <p className={`text-white text-readable ${theme}`}>📷 {fullProfile.contacts.instagram}</p>
                  )}
                </div>
              </div>
            )}
            {fullProfile?.skills && fullProfile.skills.length > 0 && (
              <div>
                <p className="text-white/60 text-sm mb-2">Навыки</p>
                <div className="flex flex-wrap gap-2">
                  {fullProfile.skills.map((skill, index) => (
                    <span
                      key={index}
                      className="px-3 py-1 bg-best-primary/20 text-best-primary rounded-full text-sm"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              </div>
            )}

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
        )}
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
