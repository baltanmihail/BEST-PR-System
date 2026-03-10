import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Loader2, AlertCircle, CheckCircle2, Calendar, ArrowLeft, Plus, X, Trash2, Edit2, RefreshCw, HardDrive, Headphones, Lightbulb, Box, ShoppingCart, Minus } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { equipmentApi, type Equipment, type EquipmentResponse, type EquipmentCategory, type EquipmentCreate } from '../services/equipment'
import { UserRole } from '../types/user'
import EquipmentCalendar from '../components/EquipmentCalendar'

interface CartItem {
  equipment: Equipment
  start_date: string
  end_date: string
}

export default function EquipmentPage() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  const [cart, setCart] = useState<CartItem[]>([])
  const [showCartModal, setShowCartModal] = useState(false)
  const [cartPurpose, setCartPurpose] = useState('')

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

  const batchMutation = useMutation({
    mutationFn: (data: { items: { equipment_id: string; start_date: string; end_date: string }[]; purpose?: string }) =>
      equipmentApi.createBatchRequests(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
      queryClient.invalidateQueries({ queryKey: ['equipment', 'requests'] })
      setCart([])
      setShowCartModal(false)
      setCartPurpose('')
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка оформления заявки')
    }
  })

  const addToCart = (equipment: Equipment) => {
    if (!isRegistered) {
      alert('Для аренды оборудования необходимо зарегистрироваться')
      navigate('/register')
      return
    }
    if (cart.find(c => c.equipment.id === equipment.id)) return
    setCart(prev => [...prev, { equipment, start_date: '', end_date: '' }])
  }

  const removeFromCart = (equipmentId: string) => {
    setCart(prev => prev.filter(c => c.equipment.id !== equipmentId))
  }

  const updateCartItem = (equipmentId: string, field: 'start_date' | 'end_date', value: string) => {
    setCart(prev => prev.map(c =>
      c.equipment.id === equipmentId ? { ...c, [field]: value } : c
    ))
  }

  const setAllDates = (field: 'start_date' | 'end_date', value: string) => {
    setCart(prev => prev.map(c => ({ ...c, [field]: value })))
  }

  const handleCartSubmit = () => {
    const incomplete = cart.find(c => !c.start_date || !c.end_date)
    if (incomplete) {
      alert('Укажите даты для всех позиций')
      return
    }
    const invalid = cart.find(c => new Date(c.end_date) < new Date(c.start_date))
    if (invalid) {
      alert(`Дата возврата раньше даты выдачи для: ${invalid.equipment.name}`)
      return
    }
    batchMutation.mutate({
      items: cart.map(c => ({
        equipment_id: c.equipment.id,
        start_date: c.start_date,
        end_date: c.end_date,
      })),
      purpose: cartPurpose || undefined,
    })
  }

  const isInCart = (equipmentId: string) => cart.some(c => c.equipment.id === equipmentId)

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

  const API_ORIGIN = import.meta.env.VITE_API_URL
    ? import.meta.env.VITE_API_URL.replace(/\/api\/v1\/?$/, '')
    : (import.meta.env.DEV ? 'http://localhost:8000' : 'https://best-pr-api.up.railway.app')

  const getPhotoUrl = (url?: string): string | undefined => {
    if (!url) return undefined
    if (url.startsWith('/api/')) return `${API_ORIGIN}${url}`
    return url
  }

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
      stabilizer: 'Стабилизатор',
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
      case 'stabilizer':
        return <RefreshCw className="h-6 w-6" />
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
    { key: 'stabilizer', label: 'Стабилизаторы' },
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

      {/* Модальное окно корзины */}
      {showCartModal && cart.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <div className={`glass-enhanced ${theme} rounded-xl p-6 w-full max-w-lg border-2 border-best-primary/50 shadow-2xl relative animate-in zoom-in-95 duration-200 max-h-[90vh] overflow-y-auto`}>
            <button
              onClick={() => setShowCartModal(false)}
              className="absolute top-4 right-4 text-white/50 hover:text-white transition-colors"
            >
              <X className="h-5 w-5" />
            </button>

            <div className="flex items-center space-x-2 mb-4">
              <ShoppingCart className="h-5 w-5 text-best-primary" />
              <h2 className={`text-xl font-bold text-white text-readable ${theme}`}>
                Оформление заявки ({cart.length} поз.)
              </h2>
            </div>

            {/* Общие даты */}
            <div className="mb-4 p-3 bg-white/5 rounded-lg border border-white/10">
              <p className="text-white/60 text-xs uppercase tracking-wider mb-2 font-medium">Общие даты (для всех позиций)</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-white/70 text-xs mb-1">Дата выдачи</label>
                  <input
                    type="date"
                    min={new Date().toISOString().split('T')[0]}
                    onChange={(e) => setAllDates('start_date', e.target.value)}
                    className={`w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-sm text-readable ${theme}`}
                  />
                </div>
                <div>
                  <label className="block text-white/70 text-xs mb-1">Дата возврата</label>
                  <input
                    type="date"
                    min={new Date().toISOString().split('T')[0]}
                    onChange={(e) => setAllDates('end_date', e.target.value)}
                    className={`w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-sm text-readable ${theme}`}
                  />
                </div>
              </div>
            </div>

            {/* Позиции */}
            <div className="space-y-3 mb-4">
              {cart.map((item) => (
                <div key={item.equipment.id} className="p-3 bg-white/5 rounded-lg border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2 flex-1 min-w-0">
                      {getPhotoUrl(item.equipment.specs?.photo_url) && (
                        <img src={getPhotoUrl(item.equipment.specs?.photo_url)} alt="" className="h-8 w-8 rounded object-contain bg-white/10" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      )}
                      <span className={`text-white text-sm font-medium truncate text-readable ${theme}`}>{item.equipment.name}</span>
                    </div>
                    <button onClick={() => removeFromCart(item.equipment.id)} className="text-red-400 hover:text-red-300 ml-2 flex-shrink-0">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="date"
                      value={item.start_date}
                      min={new Date().toISOString().split('T')[0]}
                      onChange={(e) => updateCartItem(item.equipment.id, 'start_date', e.target.value)}
                      required
                      className={`bg-white/10 text-white rounded px-2 py-1.5 border border-white/20 text-xs focus:outline-none focus:ring-1 focus:ring-best-primary text-readable ${theme}`}
                    />
                    <input
                      type="date"
                      value={item.end_date}
                      min={item.start_date || new Date().toISOString().split('T')[0]}
                      onChange={(e) => updateCartItem(item.equipment.id, 'end_date', e.target.value)}
                      required
                      className={`bg-white/10 text-white rounded px-2 py-1.5 border border-white/20 text-xs focus:outline-none focus:ring-1 focus:ring-best-primary text-readable ${theme}`}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Цель */}
            <div className="mb-4">
              <label className={`block text-white/80 mb-1.5 text-xs font-medium uppercase tracking-wider text-readable ${theme}`}>
                Название съёмки / цель
              </label>
              <input
                type="text"
                value={cartPurpose}
                onChange={(e) => setCartPurpose(e.target.value)}
                placeholder="Например: Съёмка для LBE, фотосет для ВК..."
                className={`w-full bg-white/10 text-white placeholder-white/30 rounded-lg px-3 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} text-sm`}
              />
            </div>

            <button
              onClick={handleCartSubmit}
              disabled={batchMutation.isPending}
              className="w-full bg-best-primary text-white py-3 px-4 rounded-lg font-bold hover:bg-best-primary/80 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2 shadow-lg shadow-best-primary/20"
            >
              {batchMutation.isPending ? (
                <><Loader2 className="h-4 w-4 animate-spin" /><span>Отправка...</span></>
              ) : (
                <><CheckCircle2 className="h-4 w-4" /><span>Отправить заявку ({cart.length} поз.)</span></>
              )}
            </button>
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
                {getPhotoUrl(equipment.specs?.photo_url) ? (
                  <div className="w-full h-36 rounded-xl border border-white/10 overflow-hidden bg-white/5 mb-4 flex items-center justify-center">
                    <img 
                      src={getPhotoUrl(equipment.specs?.photo_url)} 
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
                      isInCart(equipment.id) ? (
                        <button
                          onClick={() => removeFromCart(equipment.id)}
                          className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 active:scale-95 transition-all text-sm font-semibold border border-red-500/30 flex items-center space-x-2"
                        >
                          <Minus className="h-4 w-4" />
                          <span>Убрать</span>
                        </button>
                      ) : (
                        <button
                          onClick={() => addToCart(equipment)}
                          className="px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 active:scale-95 transition-all text-sm font-semibold shadow-lg shadow-best-primary/20 flex items-center space-x-2"
                        >
                          <Plus className="h-4 w-4" />
                          <span>В корзину</span>
                        </button>
                      )
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
      
      {/* Календарь занятости */}
      {isRegistered && equipmentData?.items && equipmentData.items.length > 0 && (
        <EquipmentCalendar equipmentList={equipmentData.items} />
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
                <option value="stabilizer">🎯 Стабилизатор</option>
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
      {/* Плавающая панель корзины */}
      {cart.length > 0 && !showCartModal && (
        <div className="fixed bottom-0 left-0 right-0 z-40 p-4">
          <div className={`max-w-lg mx-auto glass-enhanced ${theme} rounded-xl p-4 border-2 border-best-primary/50 shadow-2xl flex items-center justify-between`}>
            <div className="flex items-center space-x-3">
              <div className="relative">
                <ShoppingCart className="h-6 w-6 text-best-primary" />
                <span className="absolute -top-2 -right-2 bg-best-primary text-white text-xs font-bold rounded-full h-5 w-5 flex items-center justify-center">
                  {cart.length}
                </span>
              </div>
              <div>
                <p className={`text-white font-semibold text-sm text-readable ${theme}`}>
                  {cart.length} {cart.length === 1 ? 'позиция' : cart.length < 5 ? 'позиции' : 'позиций'}
                </p>
                <p className="text-white/50 text-xs truncate max-w-[200px]">
                  {cart.map(c => c.equipment.name.split(' ')[0]).join(', ')}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setCart([])}
                className="p-2 text-white/50 hover:text-red-400 transition-colors"
                title="Очистить корзину"
              >
                <Trash2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => setShowCartModal(true)}
                className="px-5 py-2.5 bg-best-primary text-white rounded-lg font-bold hover:bg-best-primary/80 active:scale-95 transition-all shadow-lg shadow-best-primary/30 text-sm"
              >
                Оформить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}