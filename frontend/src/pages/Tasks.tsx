import { useQuery } from '@tanstack/react-query'
import { CheckSquare, AlertCircle, Filter, Loader2 } from 'lucide-react'
import { tasksApi } from '../services/tasks'
import { publicApi } from '../services/public'
import TaskCard from '../components/TaskCard'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { Task } from '../types/task'

export default function Tasks() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const isRegistered = user && user.is_active

  // Используем публичный API для незарегистрированных, защищённый для зарегистрированных
  const { data, isLoading, error } = useQuery({
    queryKey: ['tasks', isRegistered],
    queryFn: async () => {
      try {
        if (isRegistered) {
          return await tasksApi.getTasks({ limit: 50 })
        } else {
          const publicTasksResponse = await publicApi.getTasks({ limit: 50 })
          // Преобразуем формат публичных задач в полный формат Task для TaskCard
          return {
            items: publicTasksResponse.items.map(task => ({
              id: task.id,
              title: task.title,
              description: undefined,
              type: task.type as Task['type'],
              event_id: undefined,
              priority: (task.priority || 'medium') as Task['priority'],
              status: (task.status || 'open') as Task['status'],
              due_date: undefined,
              created_by: '',
              created_at: (task.created_at || new Date().toISOString()) as string,
              updated_at: (task.created_at || new Date().toISOString()) as string,
              stages: [],
              assignments: [],
            } as Task)),
            total: publicTasksResponse.total,
            skip: publicTasksResponse.skip,
            limit: publicTasksResponse.limit
          }
        }
      } catch (err: any) {
        console.error('Error loading tasks:', err)
        throw err
      }
    },
    enabled: true, // Загружаем для всех
    retry: 2,
  })

  const tasks = data?.items || []

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6" data-tour="tasks-header">
        <div>
          <h1 className={`text-3xl font-bold text-white flex items-center space-x-2 text-readable ${theme}`}>
            <CheckSquare className="h-8 w-8 text-white" style={{ 
              filter: 'drop-shadow(0 0 8px rgba(30, 136, 229, 0.8)) drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))'
            }} />
            <span>Задачи</span>
          </h1>
          <p className={`text-white mt-1 text-readable ${theme}`}>Управление задачами PR-отдела</p>
        </div>
        <button 
          className="flex items-center space-x-2 bg-white/20 text-white px-4 py-2 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30"
          data-tour="task-filters"
        >
          <Filter className="h-5 w-5" />
          <span>Фильтры</span>
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
        </div>
      )}

      {error && (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 border-2 border-status-red/50 bg-red-500/20 backdrop-blur-xl`}>
          <div className="flex items-center space-x-3">
            <AlertCircle className="h-6 w-6 text-white flex-shrink-0" />
            <div>
              <p className="text-white font-semibold text-lg">Ошибка загрузки задач</p>
              <p className="text-white/80 text-sm mt-1">Проверьте подключение к API</p>
            </div>
          </div>
        </div>
      )}

      {!isLoading && !error && tasks.length === 0 && (
        <div className={`glass-enhanced ${theme} rounded-xl p-12 text-center text-white`}>
          <CheckSquare className="h-12 w-12 text-white mx-auto mb-4" />
          <p className={`text-white text-lg text-readable ${theme}`}>Нет доступных задач</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {tasks.map((task, index) => (
          <div key={task.id} data-tour={index === 0 ? "task-card" : undefined}>
            <TaskCard task={task} />
          </div>
        ))}
      </div>
    </div>
  )
}
