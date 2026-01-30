import { Calendar } from 'lucide-react'
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'

interface MobileTaskCardProps {
  task: {
    id: string
    title: string
    type: 'smm' | 'design' | 'channel' | 'prfr' | 'event'
    status: string
    dueDate: string
    image?: string
    priority?: 'low' | 'medium' | 'high' | 'critical'
  }
  onClick?: () => void
}

export default function MobileTaskCard({ task, onClick }: MobileTaskCardProps) {
  const getTypeColor = (type: string) => {
    switch (type) {
      case 'smm': return 'from-emerald-500/80 to-emerald-900/80'
      case 'design': return 'from-blue-500/80 to-blue-900/80'
      case 'channel': return 'from-orange-500/80 to-orange-900/80'
      case 'prfr': return 'from-purple-500/80 to-purple-900/80'
      case 'event': return 'from-pink-500/80 to-pink-900/80'
      default: return 'from-gray-500/80 to-gray-900/80'
    }
  }

  const getTypeLabel = (type: string) => {
    switch (type) {
      case 'smm': return 'SMM'
      case 'design': return 'Design'
      case 'channel': return 'Channel'
      case 'prfr': return 'PR-FR'
      case 'event': return 'Event'
      default: return type
    }
  }

  return (
    <div 
      onClick={onClick}
      className="relative aspect-[4/5] w-full rounded-3xl overflow-hidden shadow-lg active:scale-[0.98] transition-transform duration-200"
    >
      {/* Background Image or Gradient */}
      <div className="absolute inset-0 bg-[#1a1a2e]">
        {task.image ? (
          <img src={task.image} alt="" className="w-full h-full object-cover opacity-60" />
        ) : (
          <div className={`w-full h-full bg-gradient-to-br ${getTypeColor(task.type)}`} />
        )}
        {/* Gradient Overlay for Text Readability */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />
      </div>

      {/* Content */}
      <div className="absolute inset-0 p-5 flex flex-col justify-between">
        {/* Top: Badges */}
        <div className="flex justify-between items-start">
          <span className="px-3 py-1 bg-white/20 backdrop-blur-md rounded-full text-xs font-bold text-white uppercase tracking-wider border border-white/10">
            {getTypeLabel(task.type)}
          </span>
          {task.priority === 'critical' && (
            <span className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.6)] animate-pulse" />
          )}
        </div>

        {/* Bottom: Info */}
        <div className="space-y-3">
          <h3 className="text-2xl font-bold text-white leading-tight line-clamp-3">
            {task.title}
          </h3>
          
          <div className="flex items-center gap-4 text-white/80 text-sm">
            <div className="flex items-center gap-1.5">
              <Calendar className="h-4 w-4" />
              <span>{format(new Date(task.dueDate), 'd MMM', { locale: ru })}</span>
            </div>
            {/* 
            <div className="flex -space-x-2">
               Avatars placeholders 
              <div className="w-6 h-6 rounded-full bg-gray-600 border border-black flex items-center justify-center text-[10px]">A</div>
              <div className="w-6 h-6 rounded-full bg-gray-500 border border-black flex items-center justify-center text-[10px]">B</div>
            </div>
            */}
          </div>
        </div>
      </div>
    </div>
  )
}