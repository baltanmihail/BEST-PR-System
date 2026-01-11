import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Calendar as CalendarIcon, CalendarDays, BarChart3, ArrowLeft, ArrowRight, RefreshCw, Loader2, Filter, ChevronDown, ChevronUp, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { calendarApi, type CalendarRole, type DetailLevel } from '../services/calendar'
import { UserRole } from '../types/user'

export default function Calendar() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  // Период: Семестр, Месяц, Неделя
  const [period, setPeriod] = useState<'semester' | 'month' | 'week'>('month')
  // Представление: Таймлайн, Список
  const [presentation, setPresentation] = useState<'timeline' | 'list'>('timeline')
  const [selectedRole, setSelectedRole] = useState<CalendarRole | 'all'>('all')
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('normal')
  const [currentDate, setCurrentDate] = useState(new Date())
  const [isFiltersOpen, setIsFiltersOpen] = useState(false) // Для мобильных: сворачиваемая панель фильтров

  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  // Вычисляем диапазон дат в зависимости от периода
  const getDateRange = () => {
    const start = new Date(currentDate)
    const end = new Date(currentDate)

    if (period === 'month') {
      start.setDate(1)
      end.setMonth(end.getMonth() + 1)
      end.setDate(0)
    } else if (period === 'week') {
      const day = start.getDay()
      start.setDate(start.getDate() - day)
      end.setDate(start.getDate() + 6)
    } else if (period === 'semester') {
      // Семестр - показываем 6 месяцев
      start.setDate(1)
      end.setMonth(end.getMonth() + 6)
      end.setDate(0)
    }

    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0],
    }
  }

  const dateRange = getDateRange()

  const { data: calendarData, isLoading } = useQuery({
    queryKey: ['calendar', period, presentation, selectedRole, dateRange.start, dateRange.end, detailLevel],
    queryFn: () => {
      // Для API используем 'timeline' если представление 'timeline', иначе 'month' для списка
      const apiView = presentation === 'timeline' ? 'timeline' : 'month'
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
    if (period === 'month') {
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 1 : -1))
    } else if (period === 'week') {
      newDate.setDate(newDate.getDate() + (direction === 'next' ? 7 : -7))
    } else if (period === 'semester') {
      // Для семестра - перемещаемся на месяц
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 1 : -1))
    }
    setCurrentDate(newDate)
  }

  const getViewTitle = () => {
    if (period === 'month') {
      return currentDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
    } else if (period === 'week') {
      const weekStart = new Date(currentDate)
      const day = weekStart.getDay()
      weekStart.setDate(weekStart.getDate() - day)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 6)
      return `${weekStart.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} - ${weekEnd.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}`
    } else if (period === 'semester') {
      const start = new Date(currentDate)
      start.setDate(1)
      const end = new Date(start)
      end.setMonth(end.getMonth() + 6)
      return `Семестр: ${start.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' })} - ${end.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' })}`
    }
    return ''
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6 md:mb-8 gap-4" data-tour="calendar-header">
        <div className="flex items-center space-x-3 md:space-x-4">
          <Link
            to="/"
            className="p-2 rounded-lg hover:bg-white/10 transition-colors touch-manipulation"
            aria-label="На главную"
          >
            <CalendarIcon className="h-5 w-5 md:h-6 md:w-6 text-white" />
          </Link>
          <div>
            <h1 className={`text-2xl md:text-3xl lg:text-4xl font-bold text-readable ${theme}`}>
              Календарь
            </h1>
            <p className={`text-white/60 text-xs md:text-sm text-readable ${theme}`}>
              {getViewTitle()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isCoordinator && (
            <Link
              to="/tasks/create"
              className="flex items-center space-x-2 bg-best-primary text-white px-4 py-2.5 md:py-2 rounded-lg hover:bg-best-primary/80 transition-all card-3d border border-best-primary/50 touch-manipulation"
              data-tour="create-task-calendar"
            >
              <Plus className="h-5 w-5" />
              <span>Создать задачу</span>
            </Link>
          )}
          {isCoordinator && (
            <button
              onClick={() => syncToSheetsMutation.mutate()}
              disabled={syncToSheetsMutation.isPending}
              className="hidden md:flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 touch-manipulation"
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
      </div>

      {/* Панель управления */}
      <div className={`glass-enhanced ${theme} rounded-xl p-4 md:p-6 mb-6`}>
        {/* Мобильная версия: кнопка для открытия фильтров */}
        <div className="md:hidden mb-4">
          <button
            onClick={() => setIsFiltersOpen(!isFiltersOpen)}
            className="w-full flex items-center justify-between p-3 bg-white/10 rounded-lg hover:bg-white/20 transition-all"
          >
            <div className="flex items-center space-x-2">
              <Filter className="h-5 w-5 text-white" />
              <span className="text-white font-medium">Фильтры и настройки</span>
            </div>
            {isFiltersOpen ? (
              <ChevronUp className="h-5 w-5 text-white" />
            ) : (
              <ChevronDown className="h-5 w-5 text-white" />
            )}
          </button>
        </div>
        
        {/* Контент панели управления */}
        <div className={`flex flex-wrap items-center gap-3 md:gap-4 ${isFiltersOpen ? 'block' : 'hidden md:flex'}`}>
          {/* Навигация по датам */}
          <div className="flex items-center space-x-2 w-full md:w-auto justify-between md:justify-start">
            <div className="flex items-center space-x-2">
              <button
                onClick={() => navigateDate('prev')}
                className="p-2 rounded-lg hover:bg-white/10 transition-all touch-manipulation"
                aria-label="Предыдущий период"
              >
                <ArrowLeft className="h-5 w-5 text-white" />
              </button>
              <button
                onClick={() => {
                  const today = new Date()
                  setCurrentDate(today)
                }}
                className="px-3 md:px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all text-sm touch-manipulation"
              >
                Сегодня
              </button>
              <button
                onClick={() => navigateDate('next')}
                className="p-2 rounded-lg hover:bg-white/10 transition-all touch-manipulation"
                aria-label="Следующий период"
              >
                <ArrowRight className="h-5 w-5 text-white" />
              </button>
            </div>
            {/* Кнопка синхронизации для координаторов (мобильная версия) */}
            {isCoordinator && (
              <button
                onClick={() => syncToSheetsMutation.mutate()}
                disabled={syncToSheetsMutation.isPending}
                className="md:hidden flex items-center space-x-2 px-3 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 touch-manipulation"
              >
                {syncToSheetsMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </button>
            )}
          </div>

          {/* Выбор периода */}
          <div className="flex flex-col md:flex-row md:items-center space-y-2 md:space-y-0 md:space-x-2 w-full md:w-auto">
            <span className="text-white/60 text-sm font-medium md:font-normal">Период:</span>
            <div className="flex space-x-1 bg-white/10 rounded-lg p-1 w-full md:w-auto">
              <button
                onClick={() => {
                  setPeriod('semester')
                  setCurrentDate(new Date())
                }}
                className={`flex-1 md:flex-none px-3 py-2 md:py-1 rounded text-sm transition-all touch-manipulation ${
                  period === 'semester'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                Семестр
              </button>
              <button
                onClick={() => {
                  setPeriod('month')
                  setCurrentDate(new Date())
                }}
                className={`flex-1 md:flex-none px-3 py-2 md:py-1 rounded text-sm transition-all touch-manipulation ${
                  period === 'month'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <CalendarDays className="h-4 w-4 inline mr-1" />
                Месяц
              </button>
              <button
                onClick={() => {
                  setPeriod('week')
                  setCurrentDate(new Date())
                }}
                className={`flex-1 md:flex-none px-3 py-2 md:py-1 rounded text-sm transition-all touch-manipulation ${
                  period === 'week'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <CalendarIcon className="h-4 w-4 inline mr-1" />
                Неделя
              </button>
            </div>
          </div>

          {/* Выбор представления */}
          <div className="flex flex-col md:flex-row md:items-center space-y-2 md:space-y-0 md:space-x-2 w-full md:w-auto" data-tour="calendar-views">
            <span className="text-white/60 text-sm font-medium md:font-normal">Представление:</span>
            <div className="flex space-x-1 bg-white/10 rounded-lg p-1 w-full md:w-auto">
              <button
                onClick={() => setPresentation('timeline')}
                className={`flex-1 md:flex-none px-3 py-2 md:py-1 rounded text-sm transition-all touch-manipulation ${
                  presentation === 'timeline'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                <BarChart3 className="h-4 w-4 inline mr-1" />
                Таймлайн
              </button>
              <button
                onClick={() => setPresentation('list')}
                className={`flex-1 md:flex-none px-3 py-2 md:py-1 rounded text-sm transition-all touch-manipulation ${
                  presentation === 'list'
                    ? 'bg-best-primary text-white'
                    : 'text-white/70 hover:text-white'
                }`}
              >
                Список
              </button>
            </div>
          </div>

          {/* Фильтр по типам задач */}
          <div className="flex flex-col md:flex-row md:items-center space-y-2 md:space-y-0 md:space-x-2 w-full md:w-auto" data-tour="calendar-filters">
            <span className="text-white/60 text-sm font-medium md:font-normal">Тип задач:</span>
            <select
              value={selectedRole}
              onChange={(e) => {
                setSelectedRole(e.target.value as CalendarRole | 'all')
              }}
              className={`w-full md:w-auto bg-white/10 text-white rounded-lg px-4 py-2.5 md:py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
            >
              <option value="all">Все</option>
              <option value="smm">SMM</option>
              <option value="design">Design</option>
              <option value="channel">Channel</option>
              <option value="prfr">PR-FR</option>
            </select>
          </div>

          {/* Уровень детализации */}
          <div className="flex flex-col md:flex-row md:items-center space-y-2 md:space-y-0 md:space-x-2 w-full md:w-auto">
            <span className="text-white/60 text-sm font-medium md:font-normal">Детализация:</span>
            <select
              value={detailLevel}
              onChange={(e) => setDetailLevel(e.target.value as DetailLevel)}
              className={`w-full md:w-auto bg-white/10 text-white rounded-lg px-4 py-2.5 md:py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
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
          {presentation === 'timeline' ? (
            <TimelineView 
              calendarData={calendarData} 
              currentDate={currentDate}
              theme={theme} 
              period={period}
            />
          ) : (
            <ListView
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
  period,
}: {
  calendarData: any
  currentDate: Date
  theme: string
  period: 'semester' | 'month' | 'week'
}) {
  // Собираем все задачи
  const allTasks: any[] = []
  const allEvents: any[] = []

  if (calendarData.items) {
    allTasks.push(...calendarData.items.filter((i: any) => i.type === 'task'))
    allEvents.push(...calendarData.items.filter((i: any) => i.type === 'event'))
  }

  // Получаем сегодняшнюю дату для выделения
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  
  // Определяем диапазон дат
  const getDateRange = () => {
    const start = new Date(currentDate)
    const end = new Date(currentDate)
    
    if (period === 'semester') {
      start.setDate(1)
      end.setMonth(end.getMonth() + 6)
      end.setDate(0)
    } else if (period === 'month') {
      start.setDate(1)
      end.setMonth(end.getMonth() + 1)
      end.setDate(0)
    } else {
      const day = start.getDay()
      start.setDate(start.getDate() - day)
      start.setHours(0, 0, 0, 0)
      end.setTime(start.getTime() + 6 * 24 * 60 * 60 * 1000)
    }
    return { start, end }
  }
  
  const { start: startDate, end: endDate } = getDateRange()
  
  // Генерируем дни
  const days: Date[] = []
  const currentDay = new Date(startDate)
  while (currentDay <= endDate) {
    days.push(new Date(currentDay))
    currentDay.setDate(currentDay.getDate() + 1)
  }
  
  // Ширина одного дня в пикселях
  const dayWidth = period === 'week' ? 120 : period === 'month' ? 40 : 20
  const totalWidth = days.length * dayWidth
  
  // Функции для расчёта позиции задачи
  const getTaskPosition = (task: any) => {
    const taskStart = task.start_date ? new Date(task.start_date) : task.due_date ? new Date(task.due_date) : null
    const taskEnd = task.end_date ? new Date(task.end_date) : task.due_date ? new Date(task.due_date) : null
    
    if (!taskStart) return null
    
    const startIdx = Math.max(0, Math.floor((taskStart.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000)))
    const endIdx = taskEnd 
      ? Math.min(days.length - 1, Math.floor((taskEnd.getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000)))
      : startIdx
    
    return {
      left: startIdx * dayWidth,
      width: Math.max(dayWidth, (endIdx - startIdx + 1) * dayWidth),
    }
  }

  // Функция для проверки, является ли день сегодняшним
  const isToday = (date: Date) => {
    return date.toDateString() === today.toDateString()
  }
  
  // Группируем дни по месяцам для семестра
  const groupedDays = period === 'semester' 
    ? days.reduce((acc: { month: string; days: Date[] }[], day) => {
        const monthKey = day.toLocaleDateString('ru-RU', { month: 'short', year: 'numeric' })
        const lastGroup = acc[acc.length - 1]
        if (lastGroup && lastGroup.month === monthKey) {
          lastGroup.days.push(day)
        } else {
          acc.push({ month: monthKey, days: [day] })
        }
        return acc
      }, [])
    : null

  return (
    <div className="space-y-4">
      <h3 className={`text-lg md:text-xl font-semibold text-white mb-4 text-readable ${theme}`}>
        Таймлайн {period === 'semester' ? 'на семестр' : period === 'month' ? 'на месяц' : 'на неделю'}
      </h3>
      
      {/* Мобильный вид - карточки */}
      <div className="md:hidden space-y-3">
        {allTasks.map((task, index) => {
          const isTodayTask = task.due_date && new Date(task.due_date).toDateString() === today.toDateString()
          return (
            <div
              key={task.id || index}
              className={`glass-enhanced ${theme} rounded-lg p-3 ${isTodayTask ? 'border-2 border-best-primary' : ''}`}
            >
              <div className="flex items-center space-x-2 mb-1">
                {task.color && <div className="w-3 h-3 rounded flex-shrink-0" style={{ backgroundColor: task.color }} />}
                <h4 className={`text-white font-medium text-sm text-readable ${theme}`}>{task.title}</h4>
              </div>
              <p className="text-white/60 text-xs">
                {task.due_date ? `Дедлайн: ${new Date(task.due_date).toLocaleDateString('ru-RU')}` : 'Без дедлайна'}
              </p>
            </div>
          )
        })}
        {allTasks.length === 0 && <p className="text-white/60 text-center py-8">Нет задач на выбранный период</p>}
      </div>
      
      {/* Десктопный Gantt-вид */}
      <div className="hidden md:block overflow-x-auto">
        <div style={{ minWidth: `${Math.max(800, totalWidth + 200)}px` }}>
          {/* Заголовок с месяцами (для семестра) */}
          {period === 'semester' && groupedDays && (
            <div className="flex border-b border-white/10 mb-1">
              <div className="w-48 flex-shrink-0 p-2 bg-white/5 font-medium text-white text-sm">Задача</div>
              {groupedDays.map((group, idx) => (
                <div 
                  key={idx} 
                  className="text-center p-2 bg-white/5 text-white font-medium text-sm border-l border-white/10"
                  style={{ width: `${group.days.length * dayWidth}px` }}
                >
                  {group.month}
                </div>
              ))}
            </div>
          )}
          
          {/* Шкала дней */}
          <div className="flex border-b-2 border-white/20 sticky top-0 bg-black/50 backdrop-blur z-10">
            <div className="w-48 flex-shrink-0 p-2 font-medium text-white text-sm">
              {period !== 'semester' && 'Задача'}
            </div>
            {days.map((day, idx) => {
              const isTodayDate = isToday(day)
              const isWeekend = day.getDay() === 0 || day.getDay() === 6
              const showDate = period === 'week' || (period === 'month' && idx % 1 === 0) || (period === 'semester' && day.getDate() === 1)
              
              return (
                <div 
                  key={idx}
                  className={`text-center border-l border-white/10 ${isTodayDate ? 'bg-best-primary/30' : isWeekend ? 'bg-white/5' : ''}`}
                  style={{ width: `${dayWidth}px`, minWidth: `${dayWidth}px` }}
                >
                  {showDate && (
                    <div className={`text-xs py-1 ${isTodayDate ? 'text-best-primary font-bold' : 'text-white/70'}`}>
                      {period === 'week' 
                        ? day.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric' })
                        : day.getDate()
                      }
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          
          {/* Задачи как Gantt бары */}
          <div className="relative">
            {allTasks.map((task, index) => {
              const pos = getTaskPosition(task)
              const statusColor = task.status === 'completed' ? '#22c55e' 
                : task.status === 'in_progress' ? '#eab308' 
                : task.color || '#3b82f6'
              
              return (
                <div key={task.id || index} className="flex items-center h-10 border-b border-white/5 hover:bg-white/5">
                  {/* Название задачи */}
                  <div className="w-48 flex-shrink-0 px-2 truncate text-white text-sm" title={task.title}>
                    {task.title}
                  </div>
                  {/* Gantt полоса */}
                  <div className="flex-1 relative h-full">
                    {pos && (
                      <div
                        className="absolute top-1 bottom-1 rounded-md flex items-center px-2 text-xs text-white font-medium shadow-lg cursor-pointer hover:opacity-90 transition-opacity"
                        style={{
                          left: `${pos.left}px`,
                          width: `${pos.width}px`,
                          backgroundColor: statusColor,
                        }}
                        title={`${task.title}${task.due_date ? ` | Дедлайн: ${new Date(task.due_date).toLocaleDateString('ru-RU')}` : ''}`}
                      >
                        <span className="truncate">
                          {period === 'week' ? task.title : ''}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
            
            {/* События */}
            {allEvents.map((event, index) => {
              const eventStart = event.date_start || event.start_date
              const eventEnd = event.date_end || event.end_date
              const startIdx = eventStart 
                ? Math.max(0, Math.floor((new Date(eventStart).getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000)))
                : 0
              const endIdx = eventEnd
                ? Math.min(days.length - 1, Math.floor((new Date(eventEnd).getTime() - startDate.getTime()) / (24 * 60 * 60 * 1000)))
                : startIdx
              
              return (
                <div key={event.id || `event-${index}`} className="flex items-center h-10 border-b border-white/5 hover:bg-white/5">
                  <div className="w-48 flex-shrink-0 px-2 truncate text-purple-400 text-sm" title={event.name || event.title}>
                    🎉 {event.name || event.title}
                  </div>
                  <div className="flex-1 relative h-full">
                    <div
                      className="absolute top-1 bottom-1 rounded-md bg-purple-600 flex items-center px-2 text-xs text-white font-medium shadow-lg"
                      style={{
                        left: `${startIdx * dayWidth}px`,
                        width: `${Math.max(dayWidth, (endIdx - startIdx + 1) * dayWidth)}px`,
                      }}
                    >
                      <span className="truncate">{period === 'week' ? (event.name || event.title) : ''}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          
          {allTasks.length === 0 && allEvents.length === 0 && (
            <p className="text-white/60 text-center py-8">Нет данных на выбранный период</p>
          )}
        </div>
      </div>
    </div>
  )
}

// Компонент для представления Список
function ListView({
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
            className={`glass-enhanced ${theme} rounded-lg p-3 md:p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3 md:gap-0`}
          >
            <div className="flex-1 w-full md:w-auto">
              <div className="flex items-center space-x-2 mb-1 md:mb-1">
                {task.color && (
                  <div
                    className="w-3 h-3 rounded flex-shrink-0"
                    style={{ backgroundColor: task.color }}
                  />
                )}
                <h4 className={`text-white font-medium text-sm md:text-base text-readable ${theme} break-words`}>
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
              className={`px-3 py-1 rounded-full text-xs font-medium border flex-shrink-0 self-start md:self-auto ${
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
