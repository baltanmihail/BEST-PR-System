import { useState } from 'react'
import { Camera, Video, Mic, Package, Plus, CheckCircle2, Calendar } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'
import type { Equipment, EquipmentCategory } from '../services/equipment'

interface Equipment3DCardProps {
  equipment: Equipment
  onSelect: (equipment: Equipment) => void
  onAddToCart: (equipment: Equipment) => void
  isInCart: boolean
  suggestedAccessories: Equipment[]
}

export default function Equipment3DCard({
  equipment,
  onSelect,
  onAddToCart,
  isInCart,
  suggestedAccessories
}: Equipment3DCardProps) {
  const { theme } = useThemeStore()
  const [isHovered, setIsHovered] = useState(false)
  const [rotation, setRotation] = useState({ x: 0, y: 0 })

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isHovered) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = (e.clientY - rect.top - rect.height / 2) / 10
    const y = (e.clientX - rect.left - rect.width / 2) / 10
    setRotation({ x: -x, y })
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
    setRotation({ x: 0, y: 0 })
  }

  const getCategoryIcon = (category: EquipmentCategory) => {
    const icons: Record<EquipmentCategory, JSX.Element> = {
      camera: <Camera className="h-6 w-6 text-best-primary" />,
      lens: <Camera className="h-6 w-6 text-purple-400" />,
      lighting: <Video className="h-6 w-6 text-yellow-400" />,
      audio: <Mic className="h-6 w-6 text-green-400" />,
      tripod: <Package className="h-6 w-6 text-orange-400" />,
      accessories: <Package className="h-6 w-6 text-pink-400" />,
      storage: <Package className="h-6 w-6 text-blue-400" />,
      other: <Package className="h-6 w-6 text-gray-400" />
    }
    return icons[category] || icons.other
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available': return 'bg-green-500/20 text-green-400 border-green-500/50'
      case 'in_use': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50'
      case 'maintenance': return 'bg-red-500/20 text-red-400 border-red-500/50'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/50'
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'available': return 'Доступно'
      case 'in_use': return 'В использовании'
      case 'maintenance': return 'На обслуживании'
      default: return status
    }
  }

  return (
    <div
      className="perspective-1000"
      onMouseEnter={() => setIsHovered(true)}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      <div
        className={`glass-enhanced ${theme} rounded-xl p-6 transition-all duration-300 cursor-pointer ${
          isHovered ? 'shadow-2xl shadow-best-primary/20' : ''
        } ${isInCart ? 'ring-2 ring-best-primary' : ''}`}
        style={{
          transform: `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg) scale(${isHovered ? 1.05 : 1})`,
          transformStyle: 'preserve-3d'
        }}
      >
        {/* Изображение оборудования */}
        <div className="relative h-40 mb-4 rounded-lg overflow-hidden bg-white/5 flex items-center justify-center">
          {equipment.image_url ? (
            <img
              src={equipment.image_url}
              alt={equipment.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="text-6xl opacity-50">
              {getCategoryIcon(equipment.category)}
            </div>
          )}
          {isInCart && (
            <div className="absolute top-2 right-2 bg-best-primary text-white px-2 py-1 rounded-full text-xs font-bold">
              В корзине
            </div>
          )}
        </div>

        {/* Информация */}
        <div className="space-y-3">
          <div className="flex items-start justify-between">
            <div>
              <h3 className={`text-white font-semibold text-lg text-readable ${theme}`}>
                {equipment.name}
              </h3>
              <p className="text-white/60 text-sm">
                {equipment.quantity} шт.
              </p>
            </div>
            <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(equipment.status)}`}>
              {getStatusText(equipment.status)}
            </span>
          </div>

          {equipment.description && (
            <p className="text-white/70 text-sm line-clamp-2">{equipment.description}</p>
          )}

          {/* Кнопки */}
          <div className="flex gap-2 pt-2">
            {equipment.status === 'available' && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); onAddToCart(equipment) }}
                  disabled={isInCart}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    isInCart
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-white/10 text-white hover:bg-white/20'
                  }`}
                >
                  {isInCart ? <CheckCircle2 className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                  {isInCart ? 'Добавлено' : 'В корзину'}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onSelect(equipment) }}
                  className="px-3 py-2 bg-best-primary text-white rounded-lg text-sm font-medium hover:bg-best-primary/80 transition-all"
                >
                  <Calendar className="h-4 w-4" />
                </button>
              </>
            )}
          </div>

          {/* Рекомендуемые аксессуары */}
          {isHovered && suggestedAccessories.length > 0 && (
            <div className="pt-3 border-t border-white/10 mt-3">
              <p className="text-white/60 text-xs mb-2">Рекомендуем добавить:</p>
              <div className="flex flex-wrap gap-1">
                {suggestedAccessories.slice(0, 3).map(acc => (
                  <button
                    key={acc.id}
                    onClick={(e) => { e.stopPropagation(); onAddToCart(acc) }}
                    className="px-2 py-1 bg-white/10 text-white/80 rounded text-xs hover:bg-white/20 transition-all"
                  >
                    + {acc.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
