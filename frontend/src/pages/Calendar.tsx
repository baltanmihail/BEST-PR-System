import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Calendar as CalendarIcon, CalendarDays, BarChart3, ArrowLeft, ArrowRight, RefreshCw, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { calendarApi, type CalendarView, type CalendarRole, type DetailLevel } from '../services/calendar'
import { UserRole } from '../types/user'

export default function Calendar() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const [view, setView] = useState<CalendarView>('month')
  const [semesterView, setSemesterView] = useState<'timeline' | 'tasks'>('timeline') // Для представления "Семестр"
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
    } else if (view === 'timeline' || view === 'semester') {
      // Таймлайн/Семестр - показываем 6 месяцев (семестр)
      start.setDate(1)
      end.setMonth(end.getMonth() + 6)
      end.setDate(0)
    } else {
      // fallback - месяц
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
    queryKey: ['calendar', view, selectedRole, dateRange.start, dateRange.end, detailLevel, semesterView],
    queryFn: () => {
      // Для представления "Семестр" используем 'timeline' для API
      const apiView = view === 'semester' ? 'timeline' : view
      if (selectedRole === 'all') {
        return calendarApi.getCalendar({
          view: apiView,
          start_date: dateRange.start,
          end_date: dateRange.end,
          detail_level: detailLevel,
          include_equipment: true,
        })
      } else {
        return calendarApi.getCalendarByRole(selectedRole, {
          view: apiView,
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
    } else if (view === 'timeline' || view === 'semester') {
      // Для таймлайна и семестра - перемещаемся на месяц
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 1 : -1))
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
    } else if (view === 'timeline') {
      return 'Таймлайн'
    } else if (view === 'semester') {
      return semesterView === 'timeline' ? 'Семестр (Таймлайн)' : 'Семестр (Задачи)'
    }
    return ''
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-8" data-tour="calendar-header">
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
            data-tour="calendar-sync"
          >
            {syncToSheetsMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
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
            {view === 'semester' && (
              <div className="flex items-center space-x-2 bg-white/10 rounded-lg p-1">
                <button
                  onClick={() => setSemesterView('timeline')}
                  className={`px-3 py-1 rounded text-sm transition-all ${
                    semesterView === 'timeline'
                      ? 'bg-best-primary text-white'
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  Таймлайн
                </button>
                <button
                  onClick={() => setSemesterView('tasks')}
                  className={`px-3 py-1 rounded text-sm transition-all ${
                    semesterView === 'tasks'
                      ? 'bg-best-primary text-white'
                      : 'text-white/70 hover:text-white'
                  }`}
                >
                  Задачи
                </button>
              </div>
            )}
            <button
              onClick={() => navigateDate('next')}
              className="p-2 rounded-lg hover:bg-white/10 transition-all"
            >
              <ArrowRight className="h-5 w-5 text-white" />
            </button>
          </div>

          {/* Выбор представления */}
          <div className="flex items-center space-x-2" data-tour="calendar-views">
            <span className="text-white/60 text-sm">Представление:</span>
            <div className="flex space-x-1 bg-white/10 rounded-lg p-1">
              <button
                onClick={() => {
                  setView('month')
                  setCurrentDate(new Date()) // Сбрасываем на текущую дату
                }}
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
                onClick={() => {
                  setView('week')
                  setCurrentDate(new Date()) // Сбрасываем на текущую дату
                }}
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
                onClick={() => {
                  setView('timeline')
                  setCurrentDate(new Date()) // Сбрасываем на текущую дату
                }}
                className={`px-3 py-1 rounded text-sm transition-all ${
                  view === 'timeline'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <BarChart3 className="h-4 w-4 inline mr-1" />
                Таймлайн
              </button>
              <button
                onClick={() => {
                  setView('semester')
                  setCurrentDate(new Date()) // Сбрасываем на текущую дату
                }}
                className={`px-3 py-1 rounded text-sm transition-all ${
                  view === 'semester'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <BarChart3 className="h-4 w-4 inline mr-1" />
                Семестр
              </button>
            </div>
          </div>

          {/* Фильтр по типам задач */}
          <div className="flex items-center space-x-2" data-tour="calendar-filters">
            <span className="text-white/60 text-sm">Тип задач:</span>
            <select
              value={selectedRole}
              onChange={(e) => {
                setSelectedRole(e.target.value as CalendarRole | 'all')
                setCurrentDate(new Date()) // Сбрасываем на текущую дату
              }}
              className={`bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white`}
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
              className={`bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white`}
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
          {view === 'semester' ? (
            semesterView === 'timeline' ? (
              <TimelineView 
                calendarData={calendarData} 
                currentDate={currentDate}
                theme={theme} 
              />
            ) : (
              <div className="space-y-4">
                <h3 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
                  Задачи на семестр
                </h3>
                {/* Здесь будет список задач - можно использовать компонент из Tasks.tsx */}
                <div className="space-y-2">
                  {(calendarData.tasks || calendarData.all_items || []).map((task: any) => (
                    <div
                      key={task.id}
                      className={`glass-enhanced ${theme} rounded-lg p-4 flex items-center justify-between`}
                    >
                      <div className="flex-1">
                        <h4 className={`text-white font-medium text-readable ${theme}`}>
                          {task.title}
                        </h4>
                        <p className="text-white/60 text-sm">
                          {task.due_date
                            ? `Дедлайн: ${new Date(task.due_date).toLocaleDateString('ru-RU')}`
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
                </div>
              </div>
            )
          ) : view === 'timeline' ? (
            <TimelineView 
              calendarData={calendarData} 
              currentDate={currentDate}
              theme={theme} 
            />
          ) : (
            <MonthWeekView
              calendarData={calendarData}
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

// Компонент для Timeline представления
function TimelineView({
  calendarData,
  currentDate,
  theme,
}: {
  calendarData: any
  currentDate: Date
  theme: string
}) {
  // Собираем все задачи
  const allTasks: any[] = []
  const allEvents: any[] = []

  if (calendarData.items) {
    allTasks.push(...calendarData.items.filter((i: any) => i.type === 'task'))
    allEvents.push(...calendarData.items.filter((i: any) => i.type === 'event'))
  }

  // Создаём временную шкалу на 6 месяцев
  const months: Date[] = []
  const startMonth = new Date(currentDate)
  startMonth.setDate(1)
  for (let i = 0; i < 6; i++) {
    const month = new Date(startMonth)
    month.setMonth(startMonth.getMonth() + i)
    months.push(month)
  }

  return (
    <div className="space-y-4 overflow-x-auto">
      <h3 className={`text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
        Таймлайн на семестр
      </h3>
      <div className="min-w-[1200px]">
        {/* Шкала месяцев */}
        <div className="flex border-b-2 border-white/20 pb-2 mb-4">
          {months.map((month, idx) => (
            <div key={idx} className="flex-1 text-center">
              <div className={`text-white font-semibold text-readable ${theme}`}>
                {month.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
              </div>
            </div>
          ))}
        </div>

        {/* Задачи и события */}
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
                  {task.start_date && task.end_date
                    ? `${new Date(task.start_date).toLocaleDateString('ru-RU')} - ${new Date(task.end_date).toLocaleDateString('ru-RU')}`
                    : task.due_date
                    ? `Дедлайн: ${new Date(task.due_date).toLocaleDateString('ru-RU')}`
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
          {allTasks.length === 0 && allEvents.length === 0 && (
            <p className="text-white/60 text-center py-8">Нет данных на выбранный период</p>
          )}
        </div>
      </div>
    </div>
  )
}

// Компонент для представления Месяц/Неделя
function MonthWeekView({
  calendarData,
  theme,
}: {
  calendarData: any
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
