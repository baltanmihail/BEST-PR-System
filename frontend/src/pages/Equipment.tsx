import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Camera, Video, Mic, Loader2, AlertCircle, CheckCircle2, Calendar, ArrowLeft } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useThemeStore } from '../store/themeStore'
import { equipmentApi, type Equipment, type EquipmentRequest, type EquipmentResponse } from '../services/equipment'

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

  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'camera':
      case 'камера':
        return <Camera className="h-6 w-6" />
      case 'video':
      case 'видео':
        return <Video className="h-6 w-6" />
      case 'audio':
      case 'аудио':
        return <Mic className="h-6 w-6" />
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
      <div className="flex items-center space-x-4 mb-8">
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
        <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6 border-2 border-best-primary/50`}>
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

      {/* Список оборудования */}
      {!isLoading && equipmentData && equipmentData.items && Array.isArray(equipmentData.items) && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {equipmentData.items.map((equipment: Equipment) => (
            <div
              key={equipment.id}
              className={`glass-enhanced ${theme} rounded-xl p-6 card-3d hover:scale-105 transition-transform`}
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-best-primary/20 rounded-lg">
                    {getCategoryIcon(equipment.category)}
                  </div>
                  <div>
                    <h3 className={`text-white font-semibold text-lg text-readable ${theme}`}>
                      {equipment.name}
                    </h3>
                    <p className="text-white/60 text-sm">{equipment.category}</p>
                  </div>
                </div>
              </div>
              {equipment.description && (
                <p className={`text-white/70 text-sm mb-4 text-readable ${theme}`}>
                  {equipment.description}
                </p>
              )}
              <div className="flex items-center justify-between">
                <span
                  className={`px-3 py-1 rounded-full text-xs font-medium border ${getStatusColor(
                    equipment.status
                  )}`}
                >
                  {getStatusText(equipment.status)}
                </span>
                {isRegistered && equipment.status === 'available' && (
                  <button
                    onClick={() => handleRequestClick(equipment)}
                    className="px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all text-sm font-medium"
                  >
                    Забронировать
                  </button>
                )}
              </div>
            </div>
          ))}
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
    </div>
  )
}
