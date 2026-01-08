import { Clock, AlertCircle, MessageSquare } from 'lucide-react'
import { useParallaxHover } from '../hooks/useParallaxHover'
import { Task } from '../types/task'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { useQuery } from '@tanstack/react-query'
import { telegramChatsApi } from '../services/telegramChats'

const typeLabels = {
  smm: 'SMM',
  design: 'Дизайн',
  channel: 'Channel',
  prfr: 'PR-FR',
}

const statusLabels = {
  draft: 'Черновик',
  open: 'Открыта',
  assigned: 'Назначена',
  in_progress: 'В работе',
  review: 'На проверке',
  completed: 'Завершена',
  cancelled: 'Отменена',
}

const priorityColors = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-status-yellow/20 text-status-yellow',
  high: 'bg-status-red/20 text-status-red',
  critical: 'bg-status-red text-white',
}

interface TaskCardProps {
  task: Task
}

export default function TaskCard({ task }: TaskCardProps) {
  const parallax = useParallaxHover(8)
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  
  // Получаем информацию о чате задачи
  const { data: taskChat } = useQuery({
    queryKey: ['task-chat', task.id],
    queryFn: () => telegramChatsApi.getTaskChat(task.id),
    enabled: !!user?.is_active,
  })
  
  const isRegistered = !!user?.is_active

  return (
    <div
      ref={parallax.ref}
      style={{ transform: parallax.transform }}
      className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover`}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-3 mb-2">
            <span className="px-3 py-1 bg-best-primary/10 text-best-primary rounded-full text-sm font-medium">
              {typeLabels[task.type as keyof typeof typeLabels]}
            </span>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${priorityColors[task.priority as keyof typeof priorityColors]}`}>
              {task.priority === 'critical' ? 'Критично' : 
               task.priority === 'high' ? 'Высокий' :
               task.priority === 'medium' ? 'Средний' : 'Низкий'}
            </span>
          </div>
                <h3 className={`text-xl font-semibold text-white mb-2 text-readable ${theme}`}>
                  {task.title}
                </h3>
                <p className={`text-white mb-4 text-readable ${theme}`}>{task.description}</p>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className={`flex items-center space-x-4 text-sm text-white text-readable ${theme}`}>
          {task.due_date && (
            <div className="flex items-center space-x-1">
              <Clock className="h-4 w-4" />
              <span>До {new Date(task.due_date).toLocaleDateString('ru-RU')}</span>
            </div>
          )}
          <div className="flex items-center space-x-1">
            <AlertCircle className="h-4 w-4" />
            <span>{statusLabels[task.status as keyof typeof statusLabels]}</span>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {isRegistered && taskChat?.exists && taskChat.invite_link && (
            <a
              href={taskChat.invite_link}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-2 bg-best-primary/20 text-white px-3 py-2 rounded-lg hover:bg-best-primary/30 transition-all card-3d border border-best-primary/50"
              title="Чат задачи"
            >
              <MessageSquare className="h-4 w-4" />
              <span className="text-sm">Чат</span>
            </a>
          )}
          <button className="bg-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30">
            Взять задачу
          </button>
        </div>
      </div>
    </div>
  )
}
