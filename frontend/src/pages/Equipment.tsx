import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Video, Mic, Loader2, AlertCircle, CheckCircle2, Calendar, ArrowLeft, Plus, ShoppingCart, X } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { equipmentApi, type Equipment, type EquipmentRequest, type EquipmentResponse, type EquipmentCategory, type EquipmentCreate } from '../services/equipment'
import { UserRole } from '../types/user'
import Equipment3DCard from '../components/Equipment3DCard'

export default function Equipment() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedEquipment, setSelectedEquipment] = useState<Equipment | null>(null)
  const [showRequestForm, setShowRequestForm] = useState(false)
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

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [showEditForm, setShowEditForm] = useState(false)
  const [editingEquipment, setEditingEquipment] = useState<Equipment | null>(null)
  const [equipmentFormData, setEquipmentFormData] = useState<EquipmentCreate>({
    name: '',
    category: 'other',
    quantity: 1,
    specs: {},
  })
  
  // Корзина оборудования
  const [cart, setCart] = useState<Equipment[]>([])
  const [showCart, setShowCart] = useState(false)
  const [cartDates, setCartDates] = useState({ start_date: '', end_date: '' })
  
  // Добавление в корзину
  const addToCart = (equipment: Equipment) => {
    if (!cart.find(e => e.id === equipment.id)) {
      setCart([...cart, equipment])
    }
  }
  
  // Удаление из корзины
  const removeFromCart = (equipmentId: string) => {
    setCart(cart.filter(e => e.id !== equipmentId))
  }
  
  // Автопредложения аксессуаров
  const getSuggestedAccessories = (equipment: Equipment): Equipment[] => {
    if (!equipmentData?.items) return []
    
    const suggestions: Equipment[] = []
    
    // Для камеры предлагаем объективы и SD карты
    if (equipment.category === 'camera') {
      const lenses = equipmentData.items.filter(e => e.category === 'lens' && e.status === 'available')
      const storage = equipmentData.items.filter(e => e.category === 'storage' && e.status === 'available')
      suggestions.push(...lenses.slice(0, 2), ...storage.slice(0, 1))
    }
    
    // Для видео предлагаем свет и аудио
    if (equipment.category === 'lighting' || equipment.name.toLowerCase().includes('видео')) {
      const audio = equipmentData.items.filter(e => e.category === 'audio' && e.status === 'available')
      const tripods = equipmentData.items.filter(e => e.category === 'tripod' && e.status === 'available')
      suggestions.push(...audio.slice(0, 1), ...tripods.slice(0, 1))
    }
    
    // Для объектива предлагаем камеру
    if (equipment.category === 'lens') {
      const cameras = equipmentData.items.filter(e => e.category === 'camera' && e.status === 'available')
      suggestions.push(...cameras.slice(0, 1))
    }
    
    return suggestions.filter(s => s.id !== equipment.id && !cart.find(c => c.id === s.id))
  }
  
  // Оформление заказа из корзины
  const submitCartMutation = useMutation({
    mutationFn: async () => {
      const promises = cart.map(equipment => 
        equipmentApi.createRequest({
          equipment_id: equipment.id,
          start_date: cartDates.start_date,
          end_date: cartDates.end_date,
          purpose: `Заявка из корзины: ${cart.map(e => e.name).join(', ')}`,
        })
      )
      return Promise.all(promises)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
      queryClient.invalidateQueries({ queryKey: ['equipment', 'requests'] })
      setCart([])
      setShowCart(false)
      setCartDates({ start_date: '', end_date: '' })
      alert('Заявки успешно отправлены!')
    },
  })
  
  // Подсчёт элементов в корзине
  const cartCount = cart.length

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
        return <Mic className="h-6 w-6" />
      case 'lighting':
        return <Video className="h-6 w-6" />
      default:
        return <Camera className="h-6 w-6" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available':
        return 'bg-green-500/20 border-green-500/50 text-green-400'
      case 'rented':
        return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400'
      case 'maintenance':
        return 'bg-orange-500/20 border-orange-500/50 text-orange-400'
      case 'broken':
        return 'bg-red-500/20 border-red-500/50 text-red-400'
      default:
        return 'bg-white/10 border-white/20 text-white'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'available':
        return 'Доступно'
      case 'rented':
        return 'Выдано'
      case 'maintenance':
        return 'В ремонте'
      case 'broken':
        return 'Сломано'
      default:
        return status
    }
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
          {/* Кнопка корзины */}
          {isRegistered && (
            <button
              onClick={() => setShowCart(true)}
              className="relative flex items-center space-x-2 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
            >
              <ShoppingCart className="h-5 w-5" />
              <span className="hidden md:inline">Корзина</span>
              {cartCount > 0 && (
                <span className="absolute -top-2 -right-2 w-6 h-6 bg-best-primary text-white text-xs font-bold rounded-full flex items-center justify-center">
                  {cartCount}
                </span>
              )}
            </button>
          )}
          {isCoordinator && (
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
              <span className="hidden md:inline">Добавить оборудование</span>
            </button>
          )}
        </div>
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

      {/* Форма заявки */}
      {showRequestForm && selectedEquipment && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6 border-2 border-best-primary/50`} data-tour="equipment-request">
          <h2 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
            Заявка на аренду: {selectedEquipment.name}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Дата выдачи *
              </label>
              <input
                type="date"
                value={requestData.start_date}
                onChange={(e) =>
                  setRequestData({ ...requestData, start_date: e.target.value })
                }
                min={new Date().toISOString().split('T')[0]}
                required
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Дата возврата *
              </label>
              <input
                type="date"
                value={requestData.end_date}
                onChange={(e) =>
                  setRequestData({ ...requestData, end_date: e.target.value })
                }
                min={requestData.start_date || new Date().toISOString().split('T')[0]}
                required
                className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
              />
            </div>
            <div>
              <label className={`block text-white mb-2 text-readable ${theme}`}>
                Цель использования *
              </label>
              <textarea
                value={requestData.purpose}
                onChange={(e) =>
                  setRequestData({ ...requestData, purpose: e.target.value })
                }
                required
                placeholder="Опишите, для какой задачи нужно оборудование..."
                rows={3}
                className={`w-full bg-white/10 text-white placeholder-white/50 rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary resize-none text-readable ${theme}`}
              />
            </div>
            <div className="flex space-x-3">
              <button
                type="submit"
                disabled={createRequestMutation.isPending}
                className={`flex-1 bg-best-primary text-white py-2 px-4 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2`}
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
              <button
                type="button"
                onClick={() => {
                  setShowRequestForm(false)
                  setSelectedEquipment(null)
                }}
                className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all"
              >
                Отмена
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Загрузка */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
        </div>
      )}

      {/* Список оборудования - 3D карточки */}
      {!isLoading && equipmentData && equipmentData.items && Array.isArray(equipmentData.items) && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8" data-tour="equipment-list">
          {equipmentData.items.map((equipment: Equipment) => (
            <Equipment3DCard
              key={equipment.id}
              equipment={equipment}
              onSelect={(eq) => handleRequestClick(eq)}
              onAddToCart={addToCart}
              isInCart={cart.some(e => e.id === equipment.id)}
              suggestedAccessories={getSuggestedAccessories(equipment)}
            />
          ))}
        </div>
      )}
      
      {/* Модальное окно корзины */}
      {showCart && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className={`glass-enhanced ${theme} rounded-2xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto`}>
            <div className="flex items-center justify-between mb-6">
              <h2 className={`text-2xl font-bold text-white text-readable ${theme}`}>
                <ShoppingCart className="inline h-6 w-6 mr-2" />
                Корзина ({cart.length})
              </h2>
              <button
                onClick={() => setShowCart(false)}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="h-6 w-6 text-white" />
              </button>
            </div>
            
            {cart.length === 0 ? (
              <p className="text-white/60 text-center py-8">Корзина пуста</p>
            ) : (
              <>
                {/* Список оборудования в корзине */}
                <div className="space-y-3 mb-6">
                  {cart.map((equipment) => (
                    <div
                      key={equipment.id}
                      className="flex items-center justify-between p-3 bg-white/5 rounded-lg"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-best-primary/20 rounded-lg">
                          {getCategoryIcon(equipment.category)}
                        </div>
                        <div>
                          <p className="text-white font-medium">{equipment.name}</p>
                          <p className="text-white/60 text-sm">{getCategoryName(equipment.category)}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => removeFromCart(equipment.id)}
                        className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      >
                        <X className="h-5 w-5" />
                      </button>
                    </div>
                  ))}
                </div>
                
                {/* Выбор дат */}
                <div className="space-y-4 mb-6">
                  <div>
                    <label className={`block text-white mb-2 text-readable ${theme}`}>
                      Дата взятия *
                    </label>
                    <input
                      type="date"
                      value={cartDates.start_date}
                      onChange={(e) => setCartDates({ ...cartDates, start_date: e.target.value })}
                      min={new Date().toISOString().split('T')[0]}
                      className="w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary"
                    />
                  </div>
                  <div>
                    <label className={`block text-white mb-2 text-readable ${theme}`}>
                      Дата возврата *
                    </label>
                    <input
                      type="date"
                      value={cartDates.end_date}
                      onChange={(e) => setCartDates({ ...cartDates, end_date: e.target.value })}
                      min={cartDates.start_date || new Date().toISOString().split('T')[0]}
                      className="w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary"
                    />
                  </div>
                </div>
                
                {/* Кнопка оформления */}
                <button
                  onClick={() => {
                    if (!cartDates.start_date || !cartDates.end_date) {
                      alert('Укажите даты аренды')
                      return
                    }
                    submitCartMutation.mutate()
                  }}
                  disabled={submitCartMutation.isPending || !cartDates.start_date || !cartDates.end_date}
                  className="w-full bg-best-primary text-white py-3 px-4 rounded-lg font-semibold hover:bg-best-primary/80 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                >
                  {submitCartMutation.isPending ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      <span>Оформление...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-5 w-5" />
                      <span>Оформить заявки ({cart.length})</span>
                    </>
                  )}
                </button>
              </>
            )}
          </div>
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
