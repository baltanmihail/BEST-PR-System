import { useState, useMemo, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Calendar as CalendarIcon, RefreshCw, Loader2, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { calendarApi, type CalendarRole, type DetailLevel } from '../services/calendar'
import { UserRole } from '../types/user'
import { format, addDays, startOfWeek, endOfWeek, isSameDay, parseISO, startOfMonth, endOfMonth, addMonths } from 'date-fns'
import { ru } from 'date-fns/locale'

type ViewMode = 'week' | 'month' | 'semester'

export default function Calendar() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  
  // Состояния
  const [viewMode, setViewMode] = useState<ViewMode>('month')
  const [currentDate, setCurrentDate] = useState(new Date())
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('normal')
  const [selectedRole, setSelectedRole] = useState<CalendarRole | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [hoveredTask, setHoveredTask] = useState<any | null>(null)
  const [hoverPosition, setHoverPosition] = useState<{ x: number, y: number } | null>(null)
  
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  // Вычисляем диапазон дат
  const dateRange = useMemo(() => {
    let start = new Date(currentDate)
    let end = new Date(currentDate)
    let days = []

    if (viewMode === 'week') {
      start = startOfWeek(currentDate, { locale: ru, weekStartsOn: 1 }) // Понедельник
      end = endOfWeek(currentDate, { locale: ru, weekStartsOn: 1 })
    } else if (viewMode === 'month') {
      start = startOfMonth(currentDate)
      end = endOfMonth(currentDate)
    } else if (viewMode === 'semester') {
      // Семестр: 6 месяцев
      start = startOfMonth(currentDate)
      end = endOfMonth(addMonths(start, 5))
    }

    let day = new Date(start)
    while (day <= end) {
      days.push(new Date(day))
      day = addDays(day, 1)
    }
    return { start, end, days }
  }, [currentDate, viewMode])

  // Загрузка данных
  const { data: calendarData, isLoading } = useQuery({
    queryKey: ['calendar', viewMode, selectedRole, dateRange.start.toISOString(), dateRange.end.toISOString(), detailLevel],
    queryFn: () => {
      const startStr = dateRange.start.toISOString().split('T')[0]
      const endStr = dateRange.end.toISOString().split('T')[0]
      
      if (selectedRole === 'all') {
        return calendarApi.getCalendar({
          view: 'timeline', // Всегда берем timeline для гибкости
          start_date: startStr,
          end_date: endStr,
          detail_level: detailLevel,
          include_equipment: true,
        })
      } else {
        return calendarApi.getCalendarByRole(selectedRole, {
          view: 'timeline',
          start_date: startStr,
          end_date: endStr,
          detail_level: detailLevel,
          include_equipment: true,
        })
      }
    },
  })

  // Синхронизация с Google Sheets
  const syncToSheetsMutation = useMutation({
    mutationFn: () =>
      calendarApi.syncToSheets({
        month: currentDate.getMonth() + 1,
        year: currentDate.getFullYear(),
        role: selectedRole === 'all' ? 'all' : selectedRole,
      }),
  })

  // Фильтрация задач (поиск)
  const filteredItems = useMemo(() => {
    if (!calendarData?.items) return []
    return calendarData.items.filter((item: any) => {
      if (searchQuery && item.title && !item.title.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
  }, [calendarData, searchQuery])

  // Навигация
  const navigateDate = (direction: 'prev' | 'next') => {
    const newDate = new Date(currentDate)
    if (viewMode === 'week') {
      newDate.setDate(newDate.getDate() + (direction === 'next' ? 7 : -7))
    } else if (viewMode === 'month') {
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 1 : -1))
    } else if (viewMode === 'semester') {
      newDate.setMonth(newDate.getMonth() + (direction === 'next' ? 6 : -6))
    }
    setCurrentDate(newDate)
  }

  // Стили для задач
  const getTaskColor = (type: string, status: string) => {
    // Если задача завершена - зеленый
    if (status === 'completed') return 'bg-green-500/20 border-green-500/50 text-green-300'
    if (status === 'cancelled') return 'bg-red-500/20 border-red-500/50 text-red-300'
    
    switch (type) {
      case 'smm': return 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
      case 'design': return 'bg-blue-500/20 border-blue-500/50 text-blue-300'
      case 'channel': return 'bg-orange-500/20 border-orange-500/50 text-orange-300'
      case 'prfr': return 'bg-purple-500/20 border-purple-500/50 text-purple-300'
      case 'equipment': return 'bg-red-500/20 border-red-500/50 text-red-300'
      case 'event': return 'bg-pink-500/20 border-pink-500/50 text-pink-300'
      default: return 'bg-gray-500/20 border-gray-500/50 text-gray-300'
    }
  }

  const getTaskStyle = (item: any) => {
    const start = item.start_date ? parseISO(item.start_date) : dateRange.start
    const end = item.end_date ? parseISO(item.end_date) : (item.due_date ? parseISO(item.due_date) : start)
    
    // Ограничиваем рамками просмотра
    const effectiveStart = start < dateRange.start ? dateRange.start : start
    const effectiveEnd = end > dateRange.end ? dateRange.end : end
    
    const totalDays = dateRange.days.length
    const startOffset = Math.max(0, (effectiveStart.getTime() - dateRange.start.getTime()) / (1000 * 60 * 60 * 24))
    let duration = (effectiveEnd.getTime() - effectiveStart.getTime()) / (1000 * 60 * 60 * 24)
    
    // Если это точка во времени (start == end), даем минимальную ширину
    if (duration < 1) duration = 1
    
    return {
      left: `${(startOffset / totalDays) * 100}%`,
      width: `${(duration / totalDays) * 100}%`
    }
  }

  // Обработчик наведения
  const handleMouseEnter = (e: React.MouseEvent, item: any) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setHoverPosition({ x: rect.left, y: rect.bottom + 10 })
    setHoveredTask(item)
  }

  const handleMouseLeave = () => {
    setHoveredTask(null)
    setHoverPosition(null)
  }

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col p-4 space-y-4">
      {/* Хедер */}
      <div className={`glass-enhanced ${theme} p-4 rounded-xl flex flex-col xl:flex-row justify-between items-start xl:items-center gap-4`}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 w-full xl:w-auto">
          <div className="flex items-center gap-3">
            <CalendarIcon className="h-6 w-6 text-best-accent" />
            <div>
              <h1 className="text-2xl font-bold text-white">Календарь</h1>
              <p className="text-white/50 text-xs">
                {format(currentDate, 'LLLL yyyy', { locale: ru })}
              </p>
            </div>
          </div>
          
          <div className="flex bg-white/10 rounded-lg p-1 self-stretch sm:self-auto">
            {(['week', 'month', 'semester'] as const).map((mode) => (
              <button 
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`flex-1 sm:flex-none px-3 py-1 rounded-md text-sm transition-all ${viewMode === mode ? 'bg-best-primary text-white' : 'text-white/70 hover:text-white'}`}
              >
                {mode === 'week' ? 'Неделя' : mode === 'month' ? 'Месяц' : 'Семестр'}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3 w-full xl:w-auto">
          {/* Поиск */}
          <div className="relative flex-1 w-full sm:w-64">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-white/50" />
            <input
              type="text"
              placeholder="Поиск..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-white/30 focus:outline-none focus:border-best-primary/50 text-sm"
            />
          </div>

          {/* Фильтры */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value as any)}
              className={`flex-1 sm:flex-none bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 text-sm`}
            >
              <option value="all">Все роли</option>
              <option value="smm">SMM</option>
              <option value="design">Design</option>
              <option value="channel">Channel</option>
              <option value="prfr">PR-FR</option>
            </select>

            <select
              value={detailLevel}
              onChange={(e) => setDetailLevel(e.target.value as any)}
              className={`flex-1 sm:flex-none bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 text-sm`}
            >
              <option value="compact">Компактно</option>
              <option value="normal">Обычно</option>
              <option value="detailed">Подробно</option>
            </select>
          </div>

          {/* Навигация */}
          <div className="flex items-center gap-1 self-end sm:self-auto">
            <button onClick={() => navigateDate('prev')} className="p-2 hover:bg-white/10 rounded-lg text-white">
              <ChevronLeft className="h-5 w-5" />
            </button>
            <button onClick={() => setCurrentDate(new Date())} className="px-3 py-1 hover:bg-white/10 rounded-lg text-white text-sm">
              Сегодня
            </button>
            <button onClick={() => navigateDate('next')} className="p-2 hover:bg-white/10 rounded-lg text-white">
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>

          {/* Синхронизация (для админов) */}
          {isCoordinator && (
            <button
              onClick={() => syncToSheetsMutation.mutate()}
              disabled={syncToSheetsMutation.isPending}
              className="p-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50"
              title="Синхронизировать с Google Sheets"
            >
              {syncToSheetsMutation.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <RefreshCw className="h-5 w-5" />}
            </button>
          )}
        </div>
      </div>

      {/* Таймлайн */}
      <div className={`glass-enhanced ${theme} flex-1 rounded-xl overflow-hidden flex flex-col relative`}>
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
          </div>
        ) : (
          <>
            {/* Шапка календаря (Sticky) */}
            <div className="flex border-b border-white/10 bg-white/5 sticky top-0 z-20">
              <div className="w-48 sm:w-64 p-4 border-r border-white/10 flex-shrink-0 font-bold text-white bg-white/5 backdrop-blur-md z-30 sticky left-0">
                Задача
              </div>
              <div ref={scrollContainerRef} className="flex-1 overflow-x-auto hide-scrollbar flex">
                {dateRange.days.map((day) => {
                  const isTodayDate = isSameDay(day, new Date())
                  const isWeekend = day.getDay() === 0 || day.getDay() === 6
                  const dayWidth = viewMode === 'semester' ? 'min-w-[30px]' : 'min-w-[40px]'
                  
                  return (
                    <div 
                      key={day.toISOString()} 
                      className={`flex-1 ${dayWidth} text-center border-r border-white/5 py-2 flex flex-col items-center justify-center ${
                        isTodayDate ? 'bg-best-primary/20' : isWeekend ? 'bg-white/5' : ''
                      }`}
                    >
                      <span className="text-[10px] text-white/50 uppercase">{format(day, 'EEEEEE', { locale: ru })}</span>
                      <span className={`text-sm font-bold ${isTodayDate ? 'text-best-primary' : 'text-white'}`}>
                        {format(day, 'd')}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Тело таймлайна */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden relative">
              {filteredItems.map((item: any) => (
                <div key={item.id} className="flex border-b border-white/5 hover:bg-white/5 transition-colors group relative">
                  {/* Название задачи (Sticky Left) */}
                  <div className="w-48 sm:w-64 p-3 border-r border-white/10 flex-shrink-0 flex items-center bg-inherit sticky left-0 z-10 backdrop-blur-sm">
                    <div className="truncate text-white text-sm font-medium" title={item.title}>
                      {item.title}
                    </div>
                  </div>
                  
                  {/* Полоска задачи */}
                  <div className="flex-1 relative h-12">
                    {/* Сетка дней (фон) */}
                    <div className="absolute inset-0 flex pointer-events-none">
                      {dateRange.days.map((day) => (
                        <div 
                          key={day.toISOString()} 
                          className={`flex-1 ${viewMode === 'semester' ? 'min-w-[30px]' : 'min-w-[40px]'} border-r border-white/5 ${
                            isSameDay(day, new Date()) ? 'bg-best-primary/5' : ''
                          }`}
                        />
                      ))}
                    </div>

                    {/* Сама задача */}
                    <div 
                      className={`absolute top-2 bottom-2 rounded-md border backdrop-blur-sm flex items-center px-2 cursor-pointer hover:brightness-110 transition-all shadow-lg ${getTaskColor(item.type_task || item.type, item.status)}`}
                      style={getTaskStyle(item)}
                      onMouseEnter={(e) => handleMouseEnter(e, item)}
                      onMouseLeave={handleMouseLeave}
                    >
                      {detailLevel !== 'compact' && (
                        <span className="text-xs font-bold truncate text-white drop-shadow-md">
                          {item.title}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {filteredItems.length === 0 && (
                <div className="p-8 text-center text-white/50">
                  Нет задач в выбранном периоде
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Hover Card (Popover) */}
      {hoveredTask && hoverPosition && (
        <div 
          className={`fixed z-50 w-72 p-4 rounded-xl glass-enhanced ${theme} border border-white/20 shadow-2xl pointer-events-none animate-in fade-in zoom-in-95 duration-200`}
          style={{ 
            left: Math.min(hoverPosition.x, window.innerWidth - 300), // Чтобы не уходило за правый край
            top: Math.min(hoverPosition.y, window.innerHeight - 200)  // Чтобы не уходило за нижний край
          }}
        >
          <div className="flex items-start justify-between mb-2">
            <h4 className="text-white font-bold text-sm">{hoveredTask.title}</h4>
            <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-bold ${getTaskColor(hoveredTask.type_task || hoveredTask.type, hoveredTask.status).split(' ')[0]}`}>
              {hoveredTask.status}
            </span>
          </div>
          
          {hoveredTask.thumbnail && (
            <img src={hoveredTask.thumbnail} alt="" className="w-full h-24 object-cover rounded-lg mb-2" />
          )}
          
          <div className="space-y-1 text-xs text-white/70">
            <div className="flex items-center gap-2">
              <CalendarIcon className="h-3 w-3" />
              <span>
                {hoveredTask.start_date ? format(parseISO(hoveredTask.start_date), 'd MMM', { locale: ru }) : ''} 
                {' - '}
                {hoveredTask.end_date ? format(parseISO(hoveredTask.end_date), 'd MMM', { locale: ru }) : ''}
              </span>
            </div>
            {hoveredTask.description && (
              <p className="line-clamp-2 mt-1">{hoveredTask.description}</p>
            )}
            
            {/* Этапы (если есть) */}
            {hoveredTask.stages && hoveredTask.stages.length > 0 && (
              <div className="mt-2 pt-2 border-t border-white/10">
                <p className="font-semibold mb-1">Этапы:</p>
                {hoveredTask.stages.map((stage: any) => (
                  <div key={stage.id} className="flex justify-between items-center">
                    <span>{stage.name}</span>
                    <span className={stage.status === 'completed' ? 'text-green-400' : 'text-yellow-400'}>
                      {stage.status === 'completed' ? '✓' : '•'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
