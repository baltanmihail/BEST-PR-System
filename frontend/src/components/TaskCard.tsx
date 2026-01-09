import { useState } from 'react'
import { Clock, AlertCircle, MessageSquare, ChevronDown, ChevronUp, HelpCircle, Image as ImageIcon, Camera } from 'lucide-react'
import { useParallaxHover } from '../hooks/useParallaxHover'
import { Task } from '../types/task'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { useQuery } from '@tanstack/react-query'
import { telegramChatsApi, TaskChatResponse } from '../services/telegramChats'
import { galleryApi } from '../services/gallery'

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
  const [expanded, setExpanded] = useState(false)
  const [selectedRole, setSelectedRole] = useState<string | null>(null)
  
  // Получаем информацию о чате задачи
  const { data: taskChat } = useQuery<TaskChatResponse>({
    queryKey: ['task-chat', task.id],
    queryFn: () => telegramChatsApi.getTaskChat(task.id),
    enabled: !!user?.is_active,
  })

  // Загружаем примеры прошлых работ
  const { data: exampleProjects } = useQuery({
    queryKey: ['gallery', 'examples', task.example_project_ids],
    queryFn: async () => {
      if (!task.example_project_ids || task.example_project_ids.length === 0) return []
      const results = await Promise.all(
        task.example_project_ids.map(() => galleryApi.getGallery({ limit: 1 }))
      )
      return results.flatMap((r) => r.items)
    },
    enabled: !!task.example_project_ids && task.example_project_ids.length > 0,
  })
  
  const isRegistered = !!user?.is_active

  const getRoleName = (role: string) => {
    const names: Record<string, string> = {
      smm: 'SMM',
      design: 'Design',
      channel: 'Channel',
      prfr: 'PR-FR',
    }
    return names[role] || role
  }

  const getStageStatusColor = (status: string, color?: string) => {
    if (color) {
      const colorMap: Record<string, string> = {
        green: 'bg-green-500/20 text-green-400 border-green-500/50',
        yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
        red: 'bg-red-500/20 text-red-400 border-red-500/50',
        purple: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
        blue: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
      }
      return colorMap[color] || 'bg-white/10 text-white border-white/20'
    }
    const statusMap: Record<string, string> = {
      completed: 'bg-green-500/20 text-green-400 border-green-500/50',
      in_progress: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
      pending: 'bg-gray-500/20 text-gray-400 border-gray-500/50',
    }
    return statusMap[status] || 'bg-white/10 text-white border-white/20'
  }

  return (
    <div
      ref={parallax.ref}
      style={{ transform: parallax.transform }}
      className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover touch-manipulation`}
    >
      {/* Превью изображения */}
      {task.thumbnail_image_url && (
        <img
          src={task.thumbnail_image_url}
          alt={task.title}
          className="w-full h-48 object-cover rounded-lg mb-4"
        />
      )}

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
            {task.equipment_available && (
              <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm font-medium flex items-center space-x-1">
                <Camera className="h-3 w-3" />
                <span>Оборудование</span>
              </span>
            )}
          </div>
          <h3 className={`text-xl font-semibold text-white mb-2 text-readable ${theme}`}>
            {task.title}
          </h3>
          {task.description && (
            <p className={`text-white mb-4 text-readable ${theme}`}>{task.description}</p>
          )}
        </div>
      </div>

      {/* ТЗ по ролям */}
      {task.role_specific_requirements && Object.keys(task.role_specific_requirements).length > 0 && (
        <div className="mb-4">
          <div className="flex items-center space-x-2 mb-2">
            <span className={`text-white font-semibold text-readable ${theme}`}>ТЗ по ролям:</span>
            <div className="flex flex-wrap gap-2">
              {Object.keys(task.role_specific_requirements).map((role) => (
                <button
                  key={role}
                  onClick={() => setSelectedRole(selectedRole === role ? null : role)}
                  className={`px-3 py-1 rounded-lg text-sm transition-all ${
                    selectedRole === role
                      ? 'bg-best-primary text-white'
                      : 'bg-white/10 text-white/70 hover:bg-white/20'
                  }`}
                >
                  {getRoleName(role)}
                </button>
              ))}
            </div>
          </div>
          {selectedRole && task.role_specific_requirements[selectedRole as keyof typeof task.role_specific_requirements] && (
            <div className={`p-3 bg-white/10 rounded-lg border border-white/20 mb-2`}>
              <p className={`text-white text-readable ${theme}`}>
                {task.role_specific_requirements[selectedRole as keyof typeof task.role_specific_requirements]}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Контрольные точки */}
      {task.stages && task.stages.length > 0 && (
        <div className="mb-4">
          <h4 className={`text-white font-semibold mb-2 text-readable ${theme}`}>
            Контрольные точки:
          </h4>
          <div className="space-y-2">
            {task.stages
              .sort((a, b) => a.stage_order - b.stage_order)
              .map((stage) => (
                <div
                  key={stage.id}
                  className="flex items-center justify-between p-2 bg-white/5 rounded-lg"
                >
                  <div className="flex items-center space-x-2">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium border ${getStageStatusColor(
                        stage.status,
                        stage.status_color
                      )}`}
                    >
                      {stage.stage_name}
                    </span>
                    {stage.due_date && (
                      <span className="text-white/60 text-xs">
                        {new Date(stage.due_date).toLocaleDateString('ru-RU')}
                      </span>
                    )}
                  </div>
                  <span
                    className={`px-2 py-1 rounded text-xs font-medium border ${getStageStatusColor(
                      stage.status,
                      stage.status_color
                    )}`}
                  >
                    {stage.status === 'completed' ? '✅ Выполнено' :
                     stage.status === 'in_progress' ? '🔄 В работе' : '⏳ Не начато'}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Вопросы */}
      {task.questions && task.questions.length > 0 && (
        <div className="mb-4">
          <h4 className={`text-white font-semibold mb-2 flex items-center space-x-2 text-readable ${theme}`}>
            <HelpCircle className="h-4 w-4" />
            <span>Вопросы по задаче:</span>
          </h4>
          <ul className="space-y-1">
            {task.questions.map((question, index) => (
              <li key={index} className={`text-white/80 text-sm flex items-start space-x-2 text-readable ${theme}`}>
                <span className="text-best-primary">•</span>
                <span>{question}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Примеры прошлых работ */}
      {exampleProjects && exampleProjects.length > 0 && (
        <div className="mb-4">
          <h4 className={`text-white font-semibold mb-2 flex items-center space-x-2 text-readable ${theme}`}>
            <ImageIcon className="h-4 w-4" />
            <span>Примеры прошлых работ:</span>
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {exampleProjects.map((project) => (
              <div
                key={project.id}
                className="p-2 bg-white/10 rounded-lg cursor-pointer hover:bg-white/20 transition-all"
              >
                {project.thumbnail_url && (
                  <img
                    src={project.thumbnail_url}
                    alt={project.title}
                    className="w-full h-20 object-cover rounded mb-1"
                  />
                )}
                <p className={`text-white text-xs text-readable ${theme}`}>{project.title}</p>
              </div>
            ))}
          </div>
        </div>
      )}

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
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-2 rounded-lg hover:bg-white/10 transition-all"
          >
            {expanded ? (
              <ChevronUp className="h-4 w-4 text-white" />
            ) : (
              <ChevronDown className="h-4 w-4 text-white" />
            )}
          </button>
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
