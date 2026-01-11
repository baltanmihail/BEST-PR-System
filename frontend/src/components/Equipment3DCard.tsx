import { useState, useRef, useEffect } from 'react'
import { Camera, Video, Mic, Calendar, ShoppingCart, Plus, Eye, X, ChevronLeft, ChevronRight } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'
import type { Equipment, EquipmentCategory } from '../services/equipment'

interface Equipment3DCardProps {
  equipment: Equipment
  onSelect: (equipment: Equipment) => void
  onAddToCart: (equipment: Equipment) => void
  isInCart: boolean
  suggestedAccessories?: Equipment[]
}

export default function Equipment3DCard({
  equipment,
  onSelect,
  onAddToCart,
  isInCart,
  suggestedAccessories = [],
}: Equipment3DCardProps) {
  const { theme } = useThemeStore()
  const cardRef = useRef<HTMLDivElement>(null)
  const [rotation, setRotation] = useState({ x: 0, y: 0 })
  const [isHovered, setIsHovered] = useState(false)
  const [showDetails, setShowDetails] = useState(false)
  const [currentImageIndex, setCurrentImageIndex] = useState(0)

  // Placeholder изображения для разных категорий
  const categoryImages: Record<EquipmentCategory, string[]> = {
    camera: [
      'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=400&h=300&fit=crop',
      'https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=400&h=300&fit=crop',
    ],
    lens: [
      'https://images.unsplash.com/photo-1617005082133-548c4dd27f35?w=400&h=300&fit=crop',
    ],
    lighting: [
      'https://images.unsplash.com/photo-1565814636199-ae8133055c1c?w=400&h=300&fit=crop',
    ],
    audio: [
      'https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=400&h=300&fit=crop',
    ],
    tripod: [
      'https://images.unsplash.com/photo-1617727553252-65863c156eb0?w=400&h=300&fit=crop',
    ],
    storage: [
      'https://images.unsplash.com/photo-1597872200969-2b65d56bd16b?w=400&h=300&fit=crop',
    ],
    other: [
      'https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=400&h=300&fit=crop',
    ],
  }

  const images = equipment.image_url 
    ? [equipment.image_url] 
    : categoryImages[equipment.category] || categoryImages.other

  // 3D эффект при движении мыши
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current || !isHovered) return
    
    const rect = cardRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const centerX = rect.width / 2
    const centerY = rect.height / 2
    
    const rotateX = (y - centerY) / 10
    const rotateY = (centerX - x) / 10
    
    setRotation({ x: rotateX, y: rotateY })
  }

  const handleMouseLeave = () => {
    setIsHovered(false)
    setRotation({ x: 0, y: 0 })
  }

  const getCategoryIcon = (category: EquipmentCategory) => {
    switch (category) {
      case 'camera': return <Camera className="h-5 w-5 text-best-primary" />
      case 'lighting': return <Video className="h-5 w-5 text-yellow-400" />
      case 'audio': return <Mic className="h-5 w-5 text-green-400" />
      default: return <Camera className="h-5 w-5 text-white/60" />
    }
  }

  const getCategoryName = (category: EquipmentCategory): string => {
    const names: Record<EquipmentCategory, string> = {
      camera: 'Камера',
      lens: 'Объектив',
      lighting: 'Освещение',
      audio: 'Аудио',
      tripod: 'Штатив',
      storage: 'Накопитель',
      other: 'Другое',
    }
    return names[category] || category
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'available': return 'bg-green-500/20 text-green-400 border-green-500/50'
      case 'in_use': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50'
      case 'maintenance': return 'bg-red-500/20 text-red-400 border-red-500/50'
      default: return 'bg-white/20 text-white/60 border-white/30'
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
    <>
      {/* 3D Карточка */}
      <div
        ref={cardRef}
        className="relative perspective-1000"
        onMouseMove={handleMouseMove}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={handleMouseLeave}
        style={{ perspective: '1000px' }}
      >
        <div
          className={`glass-enhanced ${theme} rounded-2xl overflow-hidden transition-all duration-300 ${
            isHovered ? 'shadow-2xl shadow-best-primary/20' : ''
          } ${isInCart ? 'ring-2 ring-best-primary' : ''}`}
          style={{
            transform: `rotateX(${rotation.x}deg) rotateY(${rotation.y}deg) scale(${isHovered ? 1.02 : 1})`,
            transformStyle: 'preserve-3d',
            transition: 'transform 0.1s ease-out',
          }}
        >
          {/* Изображение */}
          <div className="relative h-48 overflow-hidden group">
            <img
              src={images[currentImageIndex]}
              alt={equipment.name}
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
              onError={(e) => {
                (e.target as HTMLImageElement).src = 'https://via.placeholder.com/400x300?text=No+Image'
              }}
            />
            
            {/* Градиент */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
            
            {/* Навигация по изображениям */}
            {images.length > 1 && (
              <>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length)
                  }}
                  className="absolute left-2 top-1/2 -translate-y-1/2 p-1 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <ChevronLeft className="h-4 w-4 text-white" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setCurrentImageIndex((prev) => (prev + 1) % images.length)
                  }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <ChevronRight className="h-4 w-4 text-white" />
                </button>
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex space-x-1">
                  {images.map((_, idx) => (
                    <div
                      key={idx}
                      className={`w-1.5 h-1.5 rounded-full ${idx === currentImageIndex ? 'bg-white' : 'bg-white/40'}`}
                    />
                  ))}
                </div>
              </>
            )}
            
            {/* Статус */}
            <div className="absolute top-3 left-3">
              <span className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(equipment.status)}`}>
                {getStatusText(equipment.status)}
              </span>
            </div>
            
            {/* Кнопка просмотра */}
            <button
              onClick={() => setShowDetails(true)}
              className="absolute top-3 right-3 p-2 bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/70"
            >
              <Eye className="h-4 w-4 text-white" />
            </button>
            
            {/* В корзине */}
            {isInCart && (
              <div className="absolute top-3 right-3 p-2 bg-best-primary rounded-full">
                <ShoppingCart className="h-4 w-4 text-white" />
              </div>
            )}
          </div>
          
          {/* Контент */}
          <div className="p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center space-x-2">
                <div className="p-1.5 bg-best-primary/20 rounded-lg">
                  {getCategoryIcon(equipment.category)}
                </div>
                <div>
                  <h3 className={`text-white font-semibold text-readable ${theme}`}>
                    {equipment.name}
                  </h3>
                  <p className="text-white/60 text-xs">
                    {getCategoryName(equipment.category)}
                    {equipment.quantity > 1 && ` • ${equipment.quantity} шт.`}
                  </p>
                </div>
              </div>
            </div>
            
            {equipment.description && (
              <p className={`text-white/70 text-sm mb-3 line-clamp-2 text-readable ${theme}`}>
                {equipment.description}
              </p>
            )}
            
            {/* Характеристики */}
            {equipment.specs && Object.keys(equipment.specs).length > 0 && (
              <div className="flex flex-wrap gap-1 mb-3">
                {Object.entries(equipment.specs).slice(0, 3).map(([key, value]) => (
                  <span
                    key={key}
                    className="px-2 py-0.5 bg-white/10 rounded text-xs text-white/70"
                  >
                    {key}: {String(value)}
                  </span>
                ))}
              </div>
            )}
            
            {/* Кнопки действий */}
            <div className="flex space-x-2">
              {equipment.status === 'available' && (
                <>
                  <button
                    onClick={() => onSelect(equipment)}
                    className="flex-1 flex items-center justify-center space-x-1 px-3 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all text-sm font-medium"
                  >
                    <Calendar className="h-4 w-4" />
                    <span>Забронировать</span>
                  </button>
                  <button
                    onClick={() => onAddToCart(equipment)}
                    className={`p-2 rounded-lg transition-all ${
                      isInCart 
                        ? 'bg-best-primary text-white' 
                        : 'bg-white/10 text-white hover:bg-white/20'
                    }`}
                    title={isInCart ? 'В корзине' : 'Добавить в корзину'}
                  >
                    {isInCart ? <ShoppingCart className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                  </button>
                </>
              )}
              {equipment.status !== 'available' && (
                <button
                  onClick={() => setShowDetails(true)}
                  className="flex-1 flex items-center justify-center space-x-1 px-3 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all text-sm font-medium"
                >
                  <Eye className="h-4 w-4" />
                  <span>Подробнее</span>
                </button>
              )}
            </div>
            
            {/* Предложения аксессуаров */}
            {suggestedAccessories.length > 0 && isHovered && (
              <div className="mt-3 pt-3 border-t border-white/10">
                <p className="text-white/60 text-xs mb-2">💡 Рекомендуем добавить:</p>
                <div className="flex flex-wrap gap-1">
                  {suggestedAccessories.slice(0, 2).map((acc) => (
                    <button
                      key={acc.id}
                      onClick={(e) => {
                        e.stopPropagation()
                        onAddToCart(acc)
                      }}
                      className="flex items-center space-x-1 px-2 py-1 bg-white/10 rounded text-xs text-white/80 hover:bg-white/20 transition-colors"
                    >
                      <Plus className="h-3 w-3" />
                      <span>{acc.name}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Модальное окно с деталями */}
      {showDetails && (
        <div 
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowDetails(false)}
        >
          <div 
            className={`glass-enhanced ${theme} rounded-2xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="p-3 bg-best-primary/20 rounded-xl">
                  {getCategoryIcon(equipment.category)}
                </div>
                <div>
                  <h2 className={`text-2xl font-bold text-white text-readable ${theme}`}>
                    {equipment.name}
                  </h2>
                  <p className="text-white/60">{getCategoryName(equipment.category)}</p>
                </div>
              </div>
              <button
                onClick={() => setShowDetails(false)}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
              >
                <X className="h-6 w-6 text-white" />
              </button>
            </div>
            
            {/* Галерея */}
            <div className="relative h-64 rounded-xl overflow-hidden mb-4">
              <img
                src={images[currentImageIndex]}
                alt={equipment.name}
                className="w-full h-full object-cover"
              />
              {images.length > 1 && (
                <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex space-x-2">
                  {images.map((_, idx) => (
                    <button
                      key={idx}
                      onClick={() => setCurrentImageIndex(idx)}
                      className={`w-2 h-2 rounded-full transition-colors ${
                        idx === currentImageIndex ? 'bg-white' : 'bg-white/40'
                      }`}
                    />
                  ))}
                </div>
              )}
            </div>
            
            {/* Статус и количество */}
            <div className="flex items-center space-x-3 mb-4">
              <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(equipment.status)}`}>
                {getStatusText(equipment.status)}
              </span>
              {equipment.quantity > 1 && (
                <span className="text-white/60 text-sm">
                  Количество: {equipment.quantity} шт.
                </span>
              )}
            </div>
            
            {/* Описание */}
            {equipment.description && (
              <div className="mb-4">
                <h3 className={`text-white font-semibold mb-2 text-readable ${theme}`}>Описание</h3>
                <p className="text-white/70">{equipment.description}</p>
              </div>
            )}
            
            {/* Характеристики */}
            {equipment.specs && Object.keys(equipment.specs).length > 0 && (
              <div className="mb-4">
                <h3 className={`text-white font-semibold mb-2 text-readable ${theme}`}>Характеристики</h3>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(equipment.specs).map(([key, value]) => (
                    <div key={key} className="flex justify-between p-2 bg-white/5 rounded-lg">
                      <span className="text-white/60">{key}</span>
                      <span className="text-white">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Кнопки */}
            <div className="flex space-x-3">
              {equipment.status === 'available' && (
                <>
                  <button
                    onClick={() => {
                      setShowDetails(false)
                      onSelect(equipment)
                    }}
                    className="flex-1 flex items-center justify-center space-x-2 px-4 py-3 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all font-medium"
                  >
                    <Calendar className="h-5 w-5" />
                    <span>Забронировать</span>
                  </button>
                  <button
                    onClick={() => {
                      onAddToCart(equipment)
                      setShowDetails(false)
                    }}
                    className="flex items-center justify-center space-x-2 px-4 py-3 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all font-medium"
                  >
                    <ShoppingCart className="h-5 w-5" />
                    <span>{isInCart ? 'В корзине' : 'В корзину'}</span>
                  </button>
                </>
              )}
            </div>
            
            {/* Рекомендации */}
            {suggestedAccessories.length > 0 && (
              <div className="mt-6 pt-4 border-t border-white/10">
                <h3 className={`text-white font-semibold mb-3 text-readable ${theme}`}>
                  💡 Рекомендуем добавить
                </h3>
                <div className="grid grid-cols-2 gap-2">
                  {suggestedAccessories.map((acc) => (
                    <button
                      key={acc.id}
                      onClick={() => onAddToCart(acc)}
                      className="flex items-center space-x-2 p-3 bg-white/5 rounded-lg hover:bg-white/10 transition-colors text-left"
                    >
                      <div className="p-2 bg-best-primary/20 rounded-lg">
                        {getCategoryIcon(acc.category)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium truncate">{acc.name}</p>
                        <p className="text-white/60 text-xs">{getCategoryName(acc.category)}</p>
                      </div>
                      <Plus className="h-4 w-4 text-white/60" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
