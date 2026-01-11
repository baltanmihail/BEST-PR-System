import { useQuery } from '@tanstack/react-query'
import { CheckSquare, AlertCircle, Filter, Loader2, X, ChevronDown, ChevronUp, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { tasksApi } from '../services/tasks'
import { publicApi } from '../services/public'
import TaskCard from '../components/TaskCard'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { Task } from '../types/task'
import { UserRole } from '../types/user'
import { useState, useMemo } from 'react'

export default function Tasks() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const isRegistered = user && user.is_active
  
  // Проверяем роль координатора или VP4PR
  const roleStr = typeof user?.role === 'string' ? user.role.toLowerCase() : String(user?.role || '').toLowerCase()
  const isCoordinator = user && (
    roleStr.includes('coordinator') || 
    roleStr === 'vp4pr' || 
    roleStr === UserRole.VP4PR
  )
  
  const [isFiltersOpen, setIsFiltersOpen] = useState(false)
  const [filters, setFilters] = useState<{
    type?: string
    status?: string
    priority?: string
  }>({})

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

  // Мемоизируем фильтрацию задач для оптимизации
  const filteredTasks = useMemo(() => {
    return tasks.filter(task => {
      if (filters.type && task.type !== filters.type) return false
      if (filters.status && task.status !== filters.status) return false
      if (filters.priority && task.priority !== filters.priority) return false
      return true
    })
  }, [tasks, filters.type, filters.status, filters.priority])

  const hasActiveFilters = Object.values(filters).some(v => v !== undefined && v !== '')

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6 gap-4" data-tour="tasks-header">
        <div>
          <h1 className={`text-2xl md:text-3xl font-bold text-white flex items-center space-x-2 text-readable ${theme}`}>
            <CheckSquare className="h-6 w-6 md:h-8 md:w-8 text-white" style={{ 
              filter: 'drop-shadow(0 0 8px rgba(30, 136, 229, 0.8)) drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))'
            }} />
            <span>Задачи</span>
          </h1>
          <p className={`text-white mt-1 text-sm md:text-base text-readable ${theme}`}>Управление задачами PR-отдела</p>
        </div>
        <div className="flex items-center gap-3">
          {isCoordinator && (
            <Link
              to="/tasks/create"
              className="flex items-center space-x-2 bg-best-primary text-white px-4 py-2.5 md:py-2 rounded-lg hover:bg-best-primary/80 transition-all card-3d border border-best-primary/50 touch-manipulation"
              data-tour="create-task"
            >
              <Plus className="h-5 w-5" />
              <span>Создать задачу</span>
            </Link>
          )}
          <button 
          onClick={() => setIsFiltersOpen(!isFiltersOpen)}
          className="flex items-center justify-between md:justify-center space-x-2 bg-white/20 text-white px-4 py-2.5 md:py-2 rounded-lg hover:bg-white/30 transition-all card-3d border border-white/30 touch-manipulation w-full md:w-auto"
          data-tour="task-filters"
        >
          <div className="flex items-center space-x-2">
            <Filter className="h-5 w-5" />
            <span>Фильтры</span>
            {hasActiveFilters && (
              <span className="bg-best-primary text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {Object.values(filters).filter(v => v).length}
              </span>
            )}
          </div>
          {isFiltersOpen ? (
            <ChevronUp className="h-5 w-5 md:hidden" />
          ) : (
            <ChevronDown className="h-5 w-5 md:hidden" />
          )}
        </button>
      </div>

      {/* Панель фильтров */}
      {isFiltersOpen && (
        <div className={`glass-enhanced ${theme} rounded-xl p-4 md:p-6 mb-6`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className={`text-lg font-semibold text-white text-readable ${theme}`}>Фильтры задач</h3>
            {hasActiveFilters && (
              <button
                onClick={() => setFilters({})}
                className="text-sm text-white/60 hover:text-white transition-colors flex items-center space-x-1"
              >
                <X className="h-4 w-4" />
                <span>Сбросить</span>
              </button>
            )}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Фильтр по типу */}
            <div className="flex flex-col space-y-2">
              <label className={`text-white/80 text-sm font-medium text-readable ${theme}`}>Тип задачи</label>
              <select
                value={filters.type || ''}
                onChange={(e) => setFilters({ ...filters, type: e.target.value || undefined })}
                className={`bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
              >
                <option value="">Все типы</option>
                <option value="smm">SMM</option>
                <option value="design">Design</option>
                <option value="channel">Channel</option>
                <option value="prfr">PR-FR</option>
              </select>
            </div>

            {/* Фильтр по статусу */}
            <div className="flex flex-col space-y-2">
              <label className={`text-white/80 text-sm font-medium text-readable ${theme}`}>Статус</label>
              <select
                value={filters.status || ''}
                onChange={(e) => setFilters({ ...filters, status: e.target.value || undefined })}
                className={`bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
              >
                <option value="">Все статусы</option>
                <option value="open">Открыта</option>
                <option value="in_progress">В работе</option>
                <option value="completed">Завершена</option>
                <option value="cancelled">Отменена</option>
              </select>
            </div>

            {/* Фильтр по приоритету */}
            <div className="flex flex-col space-y-2">
              <label className={`text-white/80 text-sm font-medium text-readable ${theme}`}>Приоритет</label>
              <select
                value={filters.priority || ''}
                onChange={(e) => setFilters({ ...filters, priority: e.target.value || undefined })}
                className={`bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
              >
                <option value="">Все приоритеты</option>
                <option value="low">Низкий</option>
                <option value="medium">Средний</option>
                <option value="high">Высокий</option>
                <option value="urgent">Срочный</option>
              </select>
            </div>
          </div>
        </div>
      )}

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

      {!isLoading && !error && filteredTasks.length === 0 && tasks.length > 0 && (
        <div className={`glass-enhanced ${theme} rounded-xl p-8 text-center text-white`}>
          <Filter className="h-12 w-12 text-white/60 mx-auto mb-4" />
          <p className={`text-white text-lg text-readable ${theme}`}>Нет задач, соответствующих выбранным фильтрам</p>
          <button
            onClick={() => setFilters({})}
            className="mt-4 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all"
          >
            Сбросить фильтры
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {filteredTasks.map((task, index) => (
          <div key={task.id} data-tour={index === 0 ? "task-card" : undefined}>
            <TaskCard task={task} />
          </div>
        ))}
      </div>
    </div>
  )
}
