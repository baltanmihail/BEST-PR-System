import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Loader2, AlertCircle, CheckCircle2, Calendar, ArrowLeft, Plus, X, Trash2, Edit2, RefreshCw, HardDrive, Headphones, Lightbulb, Box } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { equipmentApi, type Equipment, type EquipmentRequest, type EquipmentResponse, type EquipmentCategory, type EquipmentCreate } from '../services/equipment'
import { UserRole } from '../types/user'

export default function EquipmentPage() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedEquipment, setSelectedEquipment] = useState<Equipment | null>(null)
  const [showRequestForm, setShowRequestForm] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [requestData, setRequestData] = useState<EquipmentRequest>({
    equipment_id: '',
    start_date: '',
    end_date: '',
    purpose: '',
  })

  const isRegistered = user && user.is_active

  // Загружаем оборудование
  const { data: equipmentData, isLoading } = useQuery<EquipmentResponse>({
    queryKey: ['equipment'],
    queryFn: () => equipmentApi.getEquipment(),
    enabled: !!user, // Только для авторизованных
  })

  // Загружаем мои заявки
  const { data: myRequests } = useQuery({
    queryKey: ['equipment', 'requests', 'my'],
    queryFn: () => equipmentApi.getMyRequests(),
    enabled: !!isRegistered,
  })

  // Синхронизация с Google Sheets (для админов)
  const syncMutation = useMutation({
    mutationFn: () => equipmentApi.syncFromSheets(),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
      alert(data.message || `Синхронизация завершена: создано ${data.created || 0}, обновлено ${data.updated || 0}`)
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка синхронизации')
    }
  })

  const createRequestMutation = useMutation({
    mutationFn: (data: EquipmentRequest) => equipmentApi.createRequest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
      queryClient.invalidateQueries({ queryKey: ['equipment', 'requests'] })
      setShowRequestForm(false)
      setSelectedEquipment(null)
      setRequestData({
        equipment_id: '',
        start_date: '',
        end_date: '',
        purpose: '',
      })
    },
  })

  const handleRequestClick = (equipment: Equipment) => {
    if (!isRegistered) {
      alert('Для аренды оборудования необходимо зарегистрироваться')
      navigate('/register')
      return
    }
    setSelectedEquipment(equipment)
    setRequestData({
      ...requestData,
      equipment_id: equipment.id,
    })
    setShowRequestForm(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!requestData.start_date || !requestData.end_date) {
      alert('Укажите даты аренды')
      return
    }
    if (new Date(requestData.end_date) < new Date(requestData.start_date)) {
      alert('Дата возврата должна быть позже даты выдачи')
      return
    }
    createRequestMutation.mutate(requestData)
  }

  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  // Мутация удаления оборудования
  const deleteEquipmentMutation = useMutation({
    mutationFn: (id: string) => equipmentApi.deleteEquipment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка удаления оборудования')
    }
  })

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showEditForm, setShowEditForm] = useState(false)
  const [editingEquipment, setEditingEquipment] = useState<Equipment | null>(null)
  const [equipmentFormData, setEquipmentFormData] = useState<EquipmentCreate>({
    name: '',
    category: 'other',
    quantity: 1,
    specs: {},
  })

  const getCategoryName = (category: EquipmentCategory): string => {
    const nameMap: Record<EquipmentCategory, string> = {
      camera: 'Камера',
      lens: 'Объектив',
      lighting: 'Свет',
      audio: 'Аудио',
      tripod: 'Штатив',
      accessories: 'Аксессуары',
      storage: 'Накопитель',
      other: 'Прочее'
    }
    return nameMap[category] || category
  }

  const getCategoryIcon = (category: EquipmentCategory) => {
    switch (category) {
      case 'camera':
        return <Camera className="h-6 w-6" />
      case 'audio':
        return <Headphones className="h-6 w-6" />
      case 'lighting':
        return <Lightbulb className="h-6 w-6" />
      case 'tripod':
        return <Box className="h-6 w-6" />
      case 'storage':
        return <HardDrive className="h-6 w-6" />
      case 'lens':
        return <Camera className="h-6 w-6" />
      default:
        return <Box className="h-6 w-6" />
    }
  }
  
  const allCategories: { key: string; label: string }[] = [
    { key: 'all', label: 'Все' },
    { key: 'camera', label: 'Камеры' },
    { key: 'lens', label: 'Объективы' },
    { key: 'lighting', label: 'Свет' },
    { key: 'audio', label: 'Аудио' },
    { key: 'tripod', label: 'Штативы' },
    { key: 'storage', label: 'Накопители' },
    { key: 'accessories', label: 'Аксессуары' },
    { key: 'other', label: 'Прочее' },
  ]
  
  const filteredItems = (equipmentData?.items || []).filter((eq: Equipment) =>
    categoryFilter === 'all' || eq.category === categoryFilter
  )

  const getStatusColor = (status: string) => {
    const map: Record<string, string> = {
      available: 'bg-green-500/20 border-green-500/50 text-green-400',
      rented: 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400',
      maintenance: 'bg-orange-500/20 border-orange-500/50 text-orange-400',
      broken: 'bg-red-500/20 border-red-500/50 text-red-400',
      pending: 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400',
      approved: 'bg-green-500/20 border-green-500/50 text-green-400',
      rejected: 'bg-red-500/20 border-red-500/50 text-red-400',
      active: 'bg-blue-500/20 border-blue-500/50 text-blue-400',
      completed: 'bg-white/10 border-white/20 text-white/60',
      cancelled: 'bg-white/10 border-white/20 text-white/40',
    }
    return map[status] || 'bg-white/10 border-white/20 text-white'
  }

  const getStatusText = (status: string) => {
    const map: Record<string, string> = {
      available: 'Доступно',
      rented: 'Выдано',
      maintenance: 'В ремонте',
      broken: 'Сломано',
      pending: 'На рассмотрении',
      approved: 'Одобрено',
      rejected: 'Отклонено',
      active: 'Выдано',
      completed: 'Возвращено',
      cancelled: 'Отменено',
    }
    return map[status] || status
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-8" data-tour="equipment-header">
        <div className="flex items-center space-x-4">
          <Link
            to="/"
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <ArrowLeft className="h-6 w-6 text-white" />
          </Link>
          <div className="flex items-center space-x-3">
            <Camera className="h-8 w-8 text-best-primary" />
            <h1 className={`text-3xl md:text-4xl font-bold text-readable ${theme}`}>Оборудование</h1>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          {isCoordinator && (
            <>
              <button
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="flex items-center space-x-2 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all border border-white/10 disabled:opacity-50"
                title="Синхронизировать с Google Sheets"
              >
                {syncMutation.isPending ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <RefreshCw className="h-5 w-5" />
                )}
                <span className="hidden md:inline">Обновить</span>
              </button>
              
              <button
                onClick={() => {
                  setShowCreateForm(true)
                  setShowEditForm(false)
                  setEditingEquipment(null)
                  setEquipmentFormData({
                    name: '',
                    category: 'other',
                    quantity: 1,
                    specs: {},
                  })
                }}
                className="flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all"
              >
                <Plus className="h-5 w-5" />
                <span className="hidden md:inline">Добавить</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Фильтры по категориям */}
      <div className="flex flex-wrap gap-2 mb-6">
        {allCategories.map(cat => (
          <button
            key={cat.key}
            onClick={() => setCategoryFilter(cat.key)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
              categoryFilter === cat.key
                ? 'bg-best-primary text-white shadow-lg shadow-best-primary/20'
                : 'bg-white/10 text-white/70 hover:bg-white/20 border border-white/10'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Предупреждение для незарегистрированных */}
      {!isRegistered && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6 border-2 border-yellow-500/50 bg-yellow-500/10`}>
          <div className="flex items-center space-x-3">
            <AlertCircle className="h-6 w-6 text-yellow-400" />
            <div>
              <p className={`text-white font-semibold text-readable ${theme}`}>
                Для аренды оборудования необходимо зарегистрироваться
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

      {/* Модальное окно заявки */}
      {showRequestForm && selectedEquipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div 
            className={`glass-enhanced ${theme} rounded-xl p-6 w-full max-w-md border-2 border-best-primary/50 shadow-2xl relative animate-in zoom-in-95 duration-200`} 
            data-tour="equipment-request"
          >
            <button
              onClick={() => {
                setShowRequestForm(false)
                setSelectedEquipment(null)
              }}
              className="absolute top-4 right-4 text-white/50 hover:text-white transition-colors"
            >
              <X className="h-5 w-5" />
            </button>

            {/* Фото оборудования в модалке */}
            {selectedEquipment.specs?.photo_url && (
              <div className="w-full h-32 rounded-xl overflow-hidden bg-white/5 mb-4">
                <img 
                  src={selectedEquipment.specs.photo_url} 
                  alt={selectedEquipment.name}
                  className="w-full h-full object-contain"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                />
              </div>
            )}
            
            <h2 className={`text-xl font-bold text-white mb-1 text-readable ${theme}`}>
              Забронировать
            </h2>
            <p className="text-white/60 text-sm mb-4">{selectedEquipment.name}</p>
            
            {selectedEquipment.quantity > 1 && (
              <p className="text-white/50 text-xs mb-4">
                Доступно: {selectedEquipment.quantity} шт.
              </p>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={`block text-white/80 mb-1.5 text-xs font-medium uppercase tracking-wider text-readable ${theme}`}>
                    Дата выдачи
                  </label>
                  <input
                    type="date"
                    value={requestData.start_date}
                    onChange={(e) =>
                      setRequestData({ ...requestData, start_date: e.target.value })
                    }
                    min={new Date().toISOString().split('T')[0]}
                    required
                    className={`w-full bg-white/10 text-white rounded-lg px-3 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} text-sm`}
                  />
                </div>
                <div>
                  <label className={`block text-white/80 mb-1.5 text-xs font-medium uppercase tracking-wider text-readable ${theme}`}>
                    Дата возврата
                  </label>
                  <input
                    type="date"
                    value={requestData.end_date}
                    onChange={(e) =>
                      setRequestData({ ...requestData, end_date: e.target.value })
                    }
                    min={requestData.start_date || new Date().toISOString().split('T')[0]}
                    required
                    className={`w-full bg-white/10 text-white rounded-lg px-3 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} text-sm`}
                  />
                </div>
              </div>
              <div>
                <label className={`block text-white/80 mb-1.5 text-xs font-medium uppercase tracking-wider text-readable ${theme}`}>
                  Название съёмки / цель
                </label>
                <input
                  type="text"
                  value={requestData.purpose}
                  onChange={(e) =>
                    setRequestData({ ...requestData, purpose: e.target.value })
                  }
                  placeholder="Например: Съёмка для LBE, фотосет для ВК..."
                  className={`w-full bg-white/10 text-white placeholder-white/30 rounded-lg px-3 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} text-sm`}
                />
              </div>
              
              <button
                type="submit"
                disabled={createRequestMutation.isPending}
                className={`w-full bg-best-primary text-white py-3 px-4 rounded-lg font-bold hover:bg-best-primary/80 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 shadow-lg shadow-best-primary/20`}
              >
                {createRequestMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Отправка...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Отправить заявку</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Загрузка */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
        </div>
      )}

      {/* Список оборудования */}
      {!isLoading && equipmentData && equipmentData.items && Array.isArray(equipmentData.items) && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6" data-tour="equipment-list">
          {filteredItems.map((equipment: Equipment) => (
            <div
              key={equipment.id}
              className={`glass-enhanced ${theme} rounded-xl p-6 hover:scale-[1.02] transition-transform relative overflow-hidden group`}
            >
              {/* Фоновое свечение при наведении */}
              <div className="absolute inset-0 bg-gradient-to-br from-best-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
              
              <div className="relative z-10">
                {/* Фото оборудования (большое, сверху карточки) */}
                {equipment.specs?.photo_url ? (
                  <div className="w-full h-36 rounded-xl border border-white/10 overflow-hidden bg-white/5 mb-4 flex items-center justify-center">
                    <img 
                      src={equipment.specs.photo_url} 
                      alt={equipment.name}
                      className="max-w-full max-h-full object-contain p-2"
                      onError={(e) => {
                        const parent = (e.target as HTMLImageElement).parentElement;
                        if (parent) parent.style.display = 'none';
                      }}
                    />
                  </div>
                ) : (
                  <div className="w-full h-24 rounded-xl border border-white/5 bg-white/5 mb-4 flex items-center justify-center text-white/20">
                    {getCategoryIcon(equipment.category)}
                  </div>
                )}
                
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className={`text-white font-bold text-base text-readable ${theme} leading-tight truncate`}>
                      {equipment.name}
                    </h3>
                    <span className="text-white/50 text-xs uppercase tracking-wider font-medium">
                      {getCategoryName(equipment.category)}
                    </span>
                  </div>
                  
                  <span className={`px-2.5 py-1 rounded-lg text-[10px] uppercase font-bold tracking-wide border shadow-sm flex-shrink-0 ml-2 ${getStatusColor(equipment.status)}`}>
                    {getStatusText(equipment.status)}
                  </span>
                </div>

                {equipment.description && (
                  <p className={`text-white/70 text-sm mb-6 line-clamp-2 min-h-[2.5em] text-readable ${theme}`}>
                    {equipment.description}
                  </p>
                )}

                <div className="flex items-center justify-between mt-auto pt-4 border-t border-white/10">
                  <div className="flex items-center space-x-2 text-white/50 text-xs">
                    <span className="font-medium text-white">{equipment.quantity} шт.</span>
                    <span>в наличии</span>
                  </div>

                  <div className="flex items-center space-x-2">
                    {isCoordinator && (
                      <>
                        <button
                          onClick={() => {
                            setEditingEquipment(equipment)
                            setEquipmentFormData({
                              name: equipment.name,
                              category: equipment.category,
                              quantity: equipment.quantity,
                              specs: equipment.specs || {},
                            })
                            setShowEditForm(true)
                            setShowCreateForm(false)
                          }}
                          className="p-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
                          title="Редактировать"
                        >
                          <Edit2 className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm('Вы уверены, что хотите удалить это оборудование?')) {
                              deleteEquipmentMutation.mutate(equipment.id)
                            }
                          }}
                          className="p-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-all"
                          title="Удалить"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </>
                    )}

                    {isRegistered && equipment.status === 'available' ? (
                      <button
                        onClick={() => handleRequestClick(equipment)}
                        className="px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 active:scale-95 transition-all text-sm font-semibold shadow-lg shadow-best-primary/20 flex items-center space-x-2"
                      >
                        <Plus className="h-4 w-4" />
                        <span>В корзину</span>
                      </button>
                    ) : (
                      <button
                        disabled
                        className="px-4 py-2 bg-white/5 text-white/30 rounded-lg cursor-not-allowed text-sm font-medium border border-white/5"
                      >
                        Недоступно
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Пустое состояние */}
      {!isLoading && equipmentData?.items?.length === 0 && (
        <div className={`glass-enhanced ${theme} rounded-xl p-12 text-center`}>
          <Camera className="h-16 w-16 mx-auto mb-4 text-white/20" />
          <h3 className="text-xl font-bold text-white mb-2">Оборудование пока не добавлено</h3>
          <p className="text-white/60 mb-6">
            В данный момент список оборудования пуст. Вы можете синхронизировать его с таблицей или добавить вручную.
          </p>
          {isCoordinator && (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <button
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="px-6 py-3 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all font-semibold flex items-center space-x-2"
              >
                {syncMutation.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <RefreshCw className="h-5 w-5" />}
                <span>Синхронизировать</span>
              </button>
              <button
                onClick={() => {
                  setShowCreateForm(true)
                  setShowEditForm(false)
                  setEditingEquipment(null)
                  setEquipmentFormData({
                    name: '',
                    category: 'other',
                    quantity: 1,
                    specs: {},
                  })
                }}
                className="px-6 py-3 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all font-semibold flex items-center space-x-2"
              >
                <Plus className="h-5 w-5" />
                <span>Добавить вручную</span>
              </button>
            </div>
          )}
        </div>
      )}
      
      {/* Мои заявки */}
      {isRegistered && Array.isArray(myRequests) && myRequests.length > 0 && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 mt-6`}>
          <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
            Мои заявки
          </h2>
          <div className="space-y-3">
            {myRequests.map((request: any) => (
              <div
                key={request.id}
                className={`p-4 bg-white/10 rounded-lg border border-white/20`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className={`text-white font-medium text-readable ${theme}`}>
                      {request.equipment_name || 'Оборудование'}
                    </p>
                    <div className="flex items-center space-x-4 mt-1 text-white/70 text-sm">
                      <span className="flex items-center space-x-1">
                        <Calendar className="h-4 w-4" />
                        <span>
                          {new Date(request.start_date).toLocaleDateString('ru-RU')} -{' '}
                          {new Date(request.end_date).toLocaleDateString('ru-RU')}
                        </span>
                      </span>
                    </div>
                  </div>
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(
                      request.status
                    )}`}
                  >
                    {getStatusText(request.status)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Форма создания/редактирования оборудования (для координаторов) */}
      {(showCreateForm || showEditForm) && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6 border-2 border-best-primary/50`}>
          <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
            {showEditForm ? 'Редактировать оборудование' : 'Добавить оборудование'}
          </h2>
          <form
            onSubmit={async (e) => {
              e.preventDefault()
              try {
                if (showEditForm && editingEquipment) {
                  await equipmentApi.updateEquipment(editingEquipment.id, equipmentFormData)
                } else {
                  await equipmentApi.createEquipment(equipmentFormData)
                }
                queryClient.invalidateQueries({ queryKey: ['equipment'] })
                setShowCreateForm(false)
                setShowEditForm(false)
                setEditingEquipment(null)
                setEquipmentFormData({
                  name: '',
                  category: 'other',
                  quantity: 1,
                  specs: {},
                })
              } catch (error: any) {
                alert(error.response?.data?.detail || 'Ошибка при сохранении оборудования')
              }
            }}
            className="space-y-4"
          >
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Название *
              </label>
              <input
                type="text"
                value={equipmentFormData.name}
                onChange={(e) =>
                  setEquipmentFormData({ ...equipmentFormData, name: e.target.value })
                }
                required
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Категория *
              </label>
              <select
                value={equipmentFormData.category}
                onChange={(e) =>
                  setEquipmentFormData({ ...equipmentFormData, category: e.target.value as EquipmentCategory })
                }
                required
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              >
                <option value="camera">📷 Камера</option>
                <option value="lens">🔍 Объектив</option>
                <option value="lighting">💡 Свет</option>
                <option value="audio">🎤 Аудио</option>
                <option value="tripod">📐 Штатив</option>
                <option value="accessories">🔧 Аксессуары</option>
                <option value="storage">💾 Накопитель</option>
                <option value="other">📦 Прочее</option>
              </select>
            </div>
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Количество экземпляров *
              </label>
              <input
                type="number"
                min="1"
                value={equipmentFormData.quantity}
                onChange={(e) =>
                  setEquipmentFormData({ ...equipmentFormData, quantity: parseInt(e.target.value) || 1 })
                }
                required
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                className="flex-1 bg-best-primary text-white py-2 px-4 rounded-lg font-semibold hover:bg-best-primary/80 transition-all"
              >
                {showEditForm ? 'Сохранить' : 'Создать'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreateForm(false)
                  setShowEditForm(false)
                  setEditingEquipment(null)
                  setEquipmentFormData({
                    name: '',
                    category: 'other',
                    quantity: 1,
                    specs: {},
                  })
                }}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
              >
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}