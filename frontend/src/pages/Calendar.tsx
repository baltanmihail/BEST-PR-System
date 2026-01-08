import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Calendar as CalendarIcon, CalendarDays, Grid3x3, BarChart3, List, ArrowLeft, ArrowRight, Sync, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { calendarApi, type CalendarView, type CalendarRole, type DetailLevel } from '../services/calendar'
import { UserRole } from '../types/user'

export default function Calendar() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const [view, setView] = useState<CalendarView>('month')
  const [selectedRole, setSelectedRole] = useState<CalendarRole | 'all'>('all')
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('normal')
  const [currentDate, setCurrentDate] = useState(new Date())

  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  // Вычисляем диапазон дат в зависимости от представления
  const getDateRange = () => {
    const start = new Date(currentDate)
    const end = new Date(currentDate)

    if (view === 'month') {
      start.setDate(1)
      end.setMonth(end.getMonth() + 1)
      end.setDate(0)
    } else if (view === 'week') {
      const day = start.getDay()
      start.setDate(start.getDate() - day)
      end.setDate(start.getDate() + 6)
    } else {
      // timeline/gantt - показываем месяц
      start.setDate(1)
      end.setMonth(end.getMonth() + 1)
      end.setDate(0)
    }

    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    }
  }

  const dateRange = getDateRange()

  const { data: calendarData, isLoading } = useQuery({
    queryKey: ['calendar', view, selectedRole, dateRange.start, dateRange.end, detailLevel],
    queryFn: () => {
      if (selectedRole === 'all') {
        return calendarApi.getCalendar({
          view,
          start_date: dateRange.start,
          end_date: dateRange.end,
          detail_level: detailLevel,
          include_equipment: true,
        })
      } else {
        return calendarApi.getCalendarByRole(selectedRole, {
          view,
          start_date: dateRange.start,
          end_date: dateRange.end,
          detail_level: detailLevel,
          include_equipment: true,
        })
      }
    },
  })

  const syncToSheetsMutation = useMutation({
    mutationFn: () =>
      calendarApi.syncToSheets({
        month: currentDate.getMonth() + 1,
        year: currentDate.getFullYear(),
        role: selectedRole === 'all' ? 'all' : selectedRole,
      }),
  })

  const navigateDate = (direction: 'prev' | 'next') => {
    const newDate = new Date(currentDate)
    if (view === 'month') {
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 1 : -1))
    } else if (view === 'week') {
      newDate.setDate(newDate.getDate() + (direction === 'next' ? 7 : -7))
    }
    setCurrentDate(newDate)
  }

  const getViewTitle = () => {
    if (view === 'month') {
      return currentDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
    } else if (view === 'week') {
      const weekStart = new Date(currentDate)
      const day = weekStart.getDay()
      weekStart.setDate(weekStart.getDate() - day)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)
      return `${weekStart.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} - ${weekEnd.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}`
    }
    return 'Таймлайн'
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <Link
            to="/"
            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
          >
            <CalendarIcon className="h-6 w-6 text-white" />
          </Link>
          <div>
            <h1 className={`text-3xl md:text-4xl font-bold text-readable ${theme}`}>
              Календарь
            </h1>
            <p className={`text-white/60 text-sm text-readable ${theme}`}>
              {getViewTitle()}
            </p>
          </div>
        </div>
        {isCoordinator && (
          <button
            onClick={() => syncToSheetsMutation.mutate()}
            disabled={syncToSheetsMutation.isPending}
            className="flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50"
          >
            {syncToSheetsMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sync className="h-4 w-4" />
            )}
            <span>Синхронизировать с Sheets</span>
          </button>
        )}
      </div>

      {/* Панель управления */}
      <div className={`glass-enhanced ${theme} rounded-xl p-6 mb-6`}>
        <div className="flex flex-wrap items-center gap-4">
          {/* Навигация по датам */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => navigateDate('prev')}
              className="p-2 rounded-lg hover:bg-white/10 transition-all"
            >
              <ArrowLeft className="h-5 w-5 text-white" />
            </button>
            <button
              onClick={() => setCurrentDate(new Date())}
              className="px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all text-sm"
            >
              Сегодня
            </button>
            <button
              onClick={() => navigateDate('next')}
              className="p-2 rounded-lg hover:bg-white/10 transition-all"
            >
              <ArrowRight className="h-5 w-5 text-white" />
            </button>
          </div>

          {/* Выбор представления */}
          <div className="flex items-center space-x-2">
            <span className="text-white/60 text-sm">Представление:</span>
            <div className="flex space-x-1 bg-white/10 rounded-lg p-1">
              <button
                onClick={() => setView('month')}
                className={`px-3 py-1 rounded text-sm transition-all ${
                  view === 'month'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <CalendarDays className="h-4 w-4 inline mr-1" />
                Месяц
              </button>
              <button
                onClick={() => setView('week')}
                className={`px-3 py-1 rounded text-sm transition-all ${
                  view === 'week'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <CalendarIcon className="h-4 w-4 inline mr-1" />
                Неделя
              </button>
              <button
                onClick={() => setView('gantt')}
                className={`px-3 py-1 rounded text-sm transition-all ${
                  view === 'gantt'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <BarChart3 className="h-4 w-4 inline mr-1" />
                Gantt
              </button>
              <button
                onClick={() => setView('kanban')}
                className={`px-3 py-1 rounded text-sm transition-all ${
                  view === 'kanban'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <Grid3x3 className="h-4 w-4 inline mr-1" />
                Kanban
              </button>
            </div>
          </div>

          {/* Фильтр по ролям */}
          <div className="flex items-center space-x-2">
            <span className="text-white/60 text-sm">Роль:</span>
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value as CalendarRole | 'all')}
              className={`bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
            >
              <option value="all">Все</option>
              <option value="smm">SMM</option>
              <option value="design">Design</option>
              <option value="channel">Channel</option>
              <option value="prfr">PR-FR</option>
            </select>
          </div>

          {/* Уровень детализации */}
          <div className="flex items-center space-x-2">
            <span className="text-white/60 text-sm">Детализация:</span>
            <select
              value={detailLevel}
              onChange={(e) => setDetailLevel(e.target.value as DetailLevel)}
              className={`bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
            >
              <option value="compact">Компактно</option>
              <option value="normal">Обычно</option>
              <option value="detailed">Подробно</option>
            </select>
          </div>
        </div>
      </div>

      {/* Контент календаря */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
        </div>
      ) : calendarData ? (
        <div className={`glass-enhanced ${theme} rounded-xl p-6`}>
          {view === 'kanban' ? (
            <KanbanView columns={calendarData.columns || []} theme={theme} />
          ) : view === 'gantt' ? (
            <GanttView tasks={calendarData.tasks || calendarData.all_items || []} theme={theme} />
          ) : (
            <MonthWeekView
              calendarData={calendarData}
              view={view}
              currentDate={currentDate}
              theme={theme}
            />
          )}
        </div>
      ) : (
        <div className={`glass-enhanced ${theme} rounded-xl p-6 text-center`}>
          <p className="text-white/60">Нет данных для отображения</p>
        </div>
      )}

      {syncToSheetsMutation.isSuccess && (
        <div className={`mt-4 glass-enhanced ${theme} rounded-xl p-4 bg-green-500/20 border border-green-500/50`}>
          <p className="text-green-400">
            ✅ {syncToSheetsMutation.data?.message}
            {syncToSheetsMutation.data?.note && (
              <span className="block text-sm text-green-300 mt-1">
                {syncToSheetsMutation.data.note}
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  )
}

// Компонент для Kanban представления
function KanbanView({ columns, theme }: { columns: Array<{ status: string; title: string; tasks_count: number; tasks: any[] }>; theme: string }) {
  const getColumnColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: 'bg-gray-500/20 border-gray-500/50',
      open: 'bg-blue-500/20 border-blue-500/50',
      assigned: 'bg-purple-500/20 border-purple-500/50',
      in_progress: 'bg-yellow-500/20 border-yellow-500/50',
      review: 'bg-orange-500/20 border-orange-500/50',
      completed: 'bg-green-500/20 border-green-500/50',
      cancelled: 'bg-red-500/20 border-red-500/50',
    }
    return colors[status] || 'bg-white/10 border-white/20'
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 overflow-x-auto">
      {columns.map((column) => (
        <div
          key={column.status}
          className={`${getColumnColor(column.status)} rounded-lg p-4 border-2 min-w-[250px]`}
        >
          <h3 className={`text-white font-semibold mb-4 text-readable ${theme}`}>
            {column.title} ({column.tasks_count})
          </h3>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {column.tasks.map((task) => (
              <div
                key={task.id}
                className={`glass-enhanced ${theme} rounded-lg p-3 cursor-pointer hover:scale-105 transition-transform`}
              >
                {task.thumbnail && (
                  <img
                    src={task.thumbnail}
                    alt={task.title}
                    className="w-full h-24 object-cover rounded mb-2"
                  />
                )}
                <h4 className={`text-white font-medium text-sm text-readable ${theme}`}>
                  {task.title}
                </h4>
                {task.due_date && (
                  <p className="text-white/60 text-xs mt-1">
                    {new Date(task.due_date).toLocaleDateString('ru-RU')}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// Компонент для Gantt представления
function GanttView({ tasks, theme }: { tasks: any[]; theme: string }) {
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[800px]">
        <div className="space-y-2">
          {tasks.map((task) => (
            <div
              key={task.id}
              className={`glass-enhanced ${theme} rounded-lg p-4 flex items-center justify-between`}
            >
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-2">
                  <div
                    className="w-4 h-4 rounded"
                    style={{ backgroundColor: task.color || '#757575' }}
                  />
                  <h4 className={`text-white font-medium text-readable ${theme}`}>
                    {task.title}
                  </h4>
                </div>
                <p className="text-white/60 text-sm">
                  {task.start && task.end
                    ? `${new Date(task.start).toLocaleDateString('ru-RU')} - ${new Date(task.end).toLocaleDateString('ru-RU')}`
                    : task.start_date && task.end_date
                    ? `${new Date(task.start_date).toLocaleDateString('ru-RU')} - ${new Date(task.end_date).toLocaleDateString('ru-RU')}`
                    : task.due_date
                    ? `До ${new Date(task.due_date).toLocaleDateString('ru-RU')}`
                    : 'Без дедлайна'}
                </p>
                {task.stages && task.stages.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {task.stages.map((stage: any) => (
                      <span
                        key={stage.id}
                        className="px-2 py-1 rounded text-xs bg-white/10 text-white/70"
                      >
                        {stage.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center space-x-2">
                <span
                  className={`px-2 py-1 rounded text-xs ${
                    task.status === 'completed'
                      ? 'bg-green-500/20 text-green-400'
                      : task.status === 'in_progress'
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-blue-500/20 text-blue-400'
                  }`}
                >
                  {task.status}
                </span>
              </div>
            </div>
          ))}
          {tasks.length === 0 && (
            <p className="text-white/60 text-center py-8">Нет задач для отображения</p>
          )}
        </div>
      </div>
    </div>
  )
}

// Компонент для представления Месяц/Неделя
function MonthWeekView({
  calendarData,
  view,
  currentDate,
  theme,
}: {
  calendarData: any
  view: CalendarView
  currentDate: Date
  theme: string
}) {
  // Собираем все задачи из days
  const allTasks: any[] = []
  const allEvents: any[] = []
  const allEquipment: any[] = []

  if (calendarData.days) {
    calendarData.days.forEach((day: any) => {
      if (day.tasks) allTasks.push(...day.tasks.map((t: any) => ({ ...t, date: day.date })))
      if (day.items) allTasks.push(...day.items.filter((i: any) => i.type === 'task').map((t: any) => ({ ...t, date: day.date })))
      if (day.equipment) allEquipment.push(...day.equipment.map((e: any) => ({ ...e, date: day.date })))
    })
  }

  if (calendarData.events) {
    allEvents.push(...calendarData.events)
  }

  if (calendarData.items) {
    allTasks.push(...calendarData.items.filter((i: any) => i.type === 'task'))
    allEvents.push(...calendarData.items.filter((i: any) => i.type === 'event'))
    allEquipment.push(...calendarData.items.filter((i: any) => i.type === 'equipment'))
  }

  return (
    <div className="space-y-4">
      <h3 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
        Задачи и события
      </h3>
      <div className="space-y-2">
        {allTasks.map((task, index) => (
          <div
            key={task.id || index}
            className={`glass-enhanced ${theme} rounded-lg p-4 flex items-center justify-between`}
          >
            <div className="flex-1">
              <div className="flex items-center space-x-2 mb-1">
                {task.color && (
                  <div
                    className="w-3 h-3 rounded"
                    style={{ backgroundColor: task.color }}
                  />
                )}
                <h4 className={`text-white font-medium text-readable ${theme}`}>
                  {task.title}
                </h4>
              </div>
              <p className="text-white/60 text-sm">
                {task.date
                  ? `Дата: ${new Date(task.date).toLocaleDateString('ru-RU')}`
                  : task.due_date
                  ? `Дедлайн: ${new Date(task.due_date).toLocaleDateString('ru-RU')}`
                  : task.start_date && task.end_date
                  ? `${new Date(task.start_date).toLocaleDateString('ru-RU')} - ${new Date(task.end_date).toLocaleDateString('ru-RU')}`
                  : 'Без дедлайна'}
              </p>
            </div>
            <span
              className={`px-3 py-1 rounded-full text-xs font-medium border ${
                task.status === 'completed'
                  ? 'bg-green-500/20 text-green-400 border-green-500/50'
                  : task.status === 'in_progress'
                  ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50'
                  : 'bg-blue-500/20 text-blue-400 border-blue-500/50'
              }`}
            >
              {task.status || 'open'}
            </span>
          </div>
        ))}
        {allEvents.map((event, index) => (
          <div
            key={event.id || index}
            className={`glass-enhanced ${theme} rounded-lg p-4 border-2 border-purple-500/50`}
          >
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded bg-purple-500" />
              <h4 className={`text-white font-medium text-readable ${theme}`}>
                {event.name || event.title}
              </h4>
            </div>
            <p className="text-white/60 text-sm mt-1">
              {event.date_start || event.start_date
                ? `${new Date(event.date_start || event.start_date).toLocaleDateString('ru-RU')}${event.date_end || event.end_date ? ` - ${new Date(event.date_end || event.end_date).toLocaleDateString('ru-RU')}` : ''}`
                : 'Без даты'}
            </p>
          </div>
        ))}
        {allEquipment.map((eq, index) => (
          <div
            key={eq.id || index}
            className={`glass-enhanced ${theme} rounded-lg p-4 border-2 border-red-500/50`}
          >
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded bg-red-500" />
              <h4 className={`text-white font-medium text-readable ${theme}`}>
                Бронирование оборудования
              </h4>
            </div>
            <p className="text-white/60 text-sm mt-1">
              {eq.start_date && eq.end_date
                ? `${new Date(eq.start_date).toLocaleDateString('ru-RU')} - ${new Date(eq.end_date).toLocaleDateString('ru-RU')}`
                : 'Без даты'}
            </p>
          </div>
        ))}
        {allTasks.length === 0 && allEvents.length === 0 && allEquipment.length === 0 && (
          <p className="text-white/60 text-center py-8">Нет данных на выбранный период</p>
        )}
      </div>
    </div>
  )
}
