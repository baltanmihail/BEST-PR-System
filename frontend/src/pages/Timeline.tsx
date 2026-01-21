import { useState, useMemo, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useThemeStore } from '../store/themeStore'
import { publicApi } from '../services/public'
import { format, addDays, startOfWeek, endOfWeek, isSameDay, isWithinInterval, parseISO, startOfMonth, endOfMonth } from 'date-fns'
import { ru } from 'date-fns/locale'
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon, Search } from 'lucide-react'
import { PublicTask } from '../services/public'

type ViewMode = 'week' | 'month' | 'quarter'

export default function Timeline() {
  const { theme } = useThemeStore()
  const [viewMode, setViewMode] = useState<ViewMode>('month')
  const [currentDate, setCurrentDate] = useState(new Date())
  const [searchQuery, setSearchQuery] = useState('')
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  // Загружаем задачи (публичные, чтобы видели все)
  const { data: tasks } = useQuery({
    queryKey: ['public-tasks'],
    queryFn: () => publicApi.getTasks({ limit: 100 }),
  })

  // Вычисляем диапазон дат для отображения
  const dateRange = useMemo(() => {
    let start = new Date(currentDate)
    let end = new Date(currentDate)
    let days = []

    if (viewMode === 'week') {
      start = startOfWeek(currentDate, { locale: ru })
      end = endOfWeek(currentDate, { locale: ru })
    } else if (viewMode === 'month') {
      start = startOfMonth(currentDate)
      end = endOfMonth(currentDate)
    } else if (viewMode === 'quarter') {
      start = startOfMonth(currentDate)
      end = addDays(start, 90)
    }

    let day = start
    while (day <= end) {
      days.push(day)
      day = addDays(day, 1)
    }
    return { start, end, days }
  }, [currentDate, viewMode])

  // Фильтрация задач
  const filteredTasks = useMemo(() => {
    if (!tasks?.items) return []
    return tasks.items.filter(task => {
      if (searchQuery && !task.title.toLowerCase().includes(searchQuery.toLowerCase())) return false
      
      // Проверяем, попадает ли задача в диапазон
      const taskStart = task.created_at ? parseISO(task.created_at) : null
      const taskEnd = task.due_date ? parseISO(task.due_date) : null
      
      if (!taskStart && !taskEnd) return false
      
      // Если есть только дедлайн
      if (!taskStart && taskEnd) {
        return isWithinInterval(taskEnd, { start: dateRange.start, end: dateRange.end })
      }
      
      // Если есть старт и конец
      if (taskStart && taskEnd) {
        return (
          isWithinInterval(taskStart, { start: dateRange.start, end: dateRange.end }) ||
          isWithinInterval(taskEnd, { start: dateRange.start, end: dateRange.end }) ||
          (taskStart < dateRange.start && taskEnd > dateRange.end)
        )
      }
      
      // Если только старт (показываем как точку или короткую полоску)
      if (taskStart && !taskEnd) {
         return isWithinInterval(taskStart, { start: dateRange.start, end: dateRange.end })
      }
      
      return false
    })
  }, [tasks, searchQuery, dateRange])

  // Скролл к текущему дню при загрузке
  useEffect(() => {
    if (scrollContainerRef.current) {
      // Центрируем (упрощенно)
      // scrollContainerRef.current.scrollLeft = 0
    }
  }, [dateRange])

  const getTaskColor = (type: string) => {
    switch (type) {
      case 'smm': return 'bg-green-500/20 border-green-500/50 text-green-300'
      case 'design': return 'bg-blue-500/20 border-blue-500/50 text-blue-300'
      case 'channel': return 'bg-orange-500/20 border-orange-500/50 text-orange-300'
      case 'prfr': return 'bg-purple-500/20 border-purple-500/50 text-purple-300'
      default: return 'bg-gray-500/20 border-gray-500/50 text-gray-300'
    }
  }

  const getTaskStyle = (task: PublicTask) => {
    const taskStart = task.created_at ? parseISO(task.created_at) : dateRange.start
    const taskEnd = task.due_date ? parseISO(task.due_date) : (taskStart ? addDays(taskStart, 3) : addDays(dateRange.start, 1))
    
    // Ограничиваем рамками просмотра
    const effectiveStart = taskStart < dateRange.start ? dateRange.start : taskStart
    const effectiveEnd = taskEnd > dateRange.end ? dateRange.end : taskEnd
    
    const totalDays = dateRange.days.length
    const startOffset = Math.max(0, (effectiveStart.getTime() - dateRange.start.getTime()) / (1000 * 60 * 60 * 24))
    const duration = Math.max(1, (effectiveEnd.getTime() - effectiveStart.getTime()) / (1000 * 60 * 60 * 24) + 1)
    
    return {
      left: `${(startOffset / totalDays) * 100}%`,
      width: `${(duration / totalDays) * 100}%`
    }
  }

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col p-4 space-y-4">
      {/* Хедер */}
      <div className={`glass-enhanced ${theme} p-4 rounded-xl flex flex-col md:flex-row justify-between items-center gap-4`}>
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <CalendarIcon className="h-6 w-6 text-best-accent" />
            Таймлайн
          </h1>
          <div className="flex bg-white/10 rounded-lg p-1">
            <button 
              onClick={() => setViewMode('week')}
              className={`px-3 py-1 rounded-md text-sm transition-all ${viewMode === 'week' ? 'bg-best-primary text-white' : 'text-white/70 hover:text-white'}`}
            >
              Неделя
            </button>
            <button 
              onClick={() => setViewMode('month')}
              className={`px-3 py-1 rounded-md text-sm transition-all ${viewMode === 'month' ? 'bg-best-primary text-white' : 'text-white/70 hover:text-white'}`}
            >
              Месяц
            </button>
            <button 
              onClick={() => setViewMode('quarter')}
              className={`px-3 py-1 rounded-md text-sm transition-all ${viewMode === 'quarter' ? 'bg-best-primary text-white' : 'text-white/70 hover:text-white'}`}
            >
              Квартал
            </button>
          </div>
        </div>

        <div className="flex items-center space-x-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-white/50" />
            <input
              type="text"
              placeholder="Поиск задач..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-white/30 focus:outline-none focus:border-best-primary/50"
            />
          </div>
          <div className="flex items-center space-x-1">
            <button onClick={() => setCurrentDate(addDays(currentDate, viewMode === 'week' ? -7 : -30))} className="p-2 hover:bg-white/10 rounded-lg text-white">
              <ChevronLeft className="h-5 w-5" />
            </button>
            <span className="text-white font-medium min-w-[100px] text-center">
              {format(currentDate, viewMode === 'week' ? 'LLLL yyyy' : 'LLLL yyyy', { locale: ru })}
            </span>
            <button onClick={() => setCurrentDate(addDays(currentDate, viewMode === 'week' ? 7 : 30))} className="p-2 hover:bg-white/10 rounded-lg text-white">
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Таймлайн */}
      <div className={`glass-enhanced ${theme} flex-1 rounded-xl overflow-hidden flex flex-col relative`}>
        {/* Шапка календаря */}
        <div className="flex border-b border-white/10 bg-white/5">
          <div className="w-64 p-4 border-r border-white/10 flex-shrink-0 font-bold text-white">
            Задача
          </div>
          <div ref={scrollContainerRef} className="flex-1 overflow-x-auto hide-scrollbar flex">
            {dateRange.days.map((day) => (
              <div 
                key={day.toISOString()} 
                className={`flex-1 min-w-[40px] text-center border-r border-white/5 py-2 flex flex-col items-center justify-center ${
                  isSameDay(day, new Date()) ? 'bg-best-primary/20' : ''
                }`}
              >
                <span className="text-xs text-white/50">{format(day, 'EE', { locale: ru })}</span>
                <span className={`text-sm font-bold ${isSameDay(day, new Date()) ? 'text-best-primary' : 'text-white'}`}>
                  {format(day, 'd')}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Тело таймлайна */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden">
          {filteredTasks.map((task) => (
            <div key={task.id} className="flex border-b border-white/5 hover:bg-white/5 transition-colors group">
              {/* Название задачи */}
              <div className="w-64 p-3 border-r border-white/10 flex-shrink-0 flex items-center">
                <div className="truncate text-white text-sm font-medium" title={task.title}>
                  {task.title}
                </div>
              </div>
              
              {/* Полоска задачи */}
              <div className="flex-1 relative h-12">
                {/* Сетка дней (фон) */}
                <div className="absolute inset-0 flex pointer-events-none">
                  {dateRange.days.map((day) => (
                    <div 
                      key={day.toISOString()} 
                      className={`flex-1 min-w-[40px] border-r border-white/5 ${
                        isSameDay(day, new Date()) ? 'bg-best-primary/5' : ''
                      }`}
                    />
                  ))}
                </div>

                {/* Сама задача */}
                <div 
                  className={`absolute top-2 bottom-2 rounded-md border backdrop-blur-sm flex items-center px-2 cursor-pointer hover:brightness-110 transition-all shadow-lg ${getTaskColor(task.type)}`}
                  style={getTaskStyle(task)}
                >
                  <span className="text-xs font-bold truncate text-white drop-shadow-md">
                    {task.title}
                  </span>
                </div>
              </div>
            </div>
          ))}
          
          {filteredTasks.length === 0 && (
            <div className="p-8 text-center text-white/50">
              Нет задач в выбранном периоде
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
