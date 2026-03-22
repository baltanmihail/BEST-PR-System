import { useState, useMemo, useRef, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Calendar as CalendarIcon, RefreshCw, Loader2, ChevronLeft, ChevronRight, Search, Users, User as UserIcon, X } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { calendarApi, type CalendarRole, type DetailLevel } from '../services/calendar'
import { UserRole } from '../types/user'
import { format, addDays, startOfWeek, endOfWeek, isSameDay, parseISO, startOfMonth, endOfMonth, addMonths, differenceInDays } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useNavigate } from 'react-router-dom'

type ViewMode = 'week' | 'month' | 'semester'

interface GanttStage {
  id: string
  name: string
  start: Date
  end: Date
  color: 'green' | 'yellow' | 'red' | 'purple' | 'blue'
  status: string
}

interface GanttTask {
  id: string
  title: string
  type: string
  status: string
  priority: string
  start: Date
  end: Date
  stages: GanttStage[]
  assignees: string[]
  assigneeNames: string[]
  description?: string
}

interface PersonRow {
  userId: string
  name: string
  role: string
  tasks: GanttTask[]
}

const stageColorMap: Record<string, string> = {
  green: 'bg-green-500',
  yellow: 'bg-yellow-500',
  red: 'bg-red-500',
  purple: 'bg-purple-500',
  blue: 'bg-blue-500',
}

const stageColorBorder: Record<string, string> = {
  green: 'border-green-400',
  yellow: 'border-yellow-400',
  red: 'border-red-400',
  purple: 'border-purple-400',
  blue: 'border-blue-400',
}

const stageLabelMap: Record<string, string> = {
  green: 'Процесс',
  yellow: 'Согласование',
  red: 'Дедлайн',
  purple: 'Ревью',
  blue: 'Буфер',
}

export default function Calendar() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const [viewMode, setViewMode] = useState<ViewMode>('month')
  const [currentDate, setCurrentDate] = useState(new Date())
  const [detailLevel, setDetailLevel] = useState<DetailLevel>('normal')
  const [selectedRole, setSelectedRole] = useState<CalendarRole | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [showMyOnly, setShowMyOnly] = useState(false)
  const [hoveredTask, setHoveredTask] = useState<any | null>(null)
  const [hoverPosition, setHoverPosition] = useState<{ x: number; y: number } | null>(null)
  const [selectedTask, setSelectedTask] = useState<any | null>(null)

  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  const dateRange = useMemo(() => {
    let start: Date, end: Date
    if (viewMode === 'week') {
      start = startOfWeek(currentDate, { locale: ru, weekStartsOn: 1 })
      end = endOfWeek(currentDate, { locale: ru, weekStartsOn: 1 })
    } else if (viewMode === 'month') {
      start = startOfMonth(currentDate)
      end = endOfMonth(currentDate)
    } else {
      start = startOfMonth(currentDate)
      end = endOfMonth(addMonths(start, 5))
    }
    const days: Date[] = []
    let day = new Date(start)
    while (day <= end) {
      days.push(new Date(day))
      day = addDays(day, 1)
    }
    return { start, end, days }
  }, [currentDate, viewMode])

  // Months header for multi-month views
  const monthHeaders = useMemo(() => {
    const headers: { label: string; span: number; start: number }[] = []
    let currentMonth = -1
    let currentStart = 0
    let currentSpan = 0
    dateRange.days.forEach((day, i) => {
      const m = day.getMonth()
      if (m !== currentMonth) {
        if (currentSpan > 0) headers.push({ label: format(dateRange.days[currentStart], 'LLLL', { locale: ru }), span: currentSpan, start: currentStart })
        currentMonth = m
        currentStart = i
        currentSpan = 1
      } else {
        currentSpan++
      }
    })
    if (currentSpan > 0) headers.push({ label: format(dateRange.days[currentStart], 'LLLL', { locale: ru }), span: currentSpan, start: currentStart })
    return headers
  }, [dateRange.days])

  const { data: calendarData, isLoading } = useQuery({
    queryKey: ['calendar', viewMode, selectedRole, dateRange.start.toISOString(), dateRange.end.toISOString(), detailLevel],
    queryFn: () => {
      const startStr = dateRange.start.toISOString().split('T')[0]
      const endStr = dateRange.end.toISOString().split('T')[0]
      if (selectedRole === 'all') {
        return calendarApi.getCalendar({ view: 'timeline', start_date: startStr, end_date: endStr, detail_level: detailLevel, include_equipment: true })
      }
      return calendarApi.getCalendarByRole(selectedRole, { view: 'timeline', start_date: startStr, end_date: endStr, detail_level: detailLevel, include_equipment: true })
    },
  })

  const syncMutation = useMutation({
    mutationFn: () => calendarApi.syncToSheets({ month: currentDate.getMonth() + 1, year: currentDate.getFullYear(), role: selectedRole === 'all' ? 'all' : selectedRole }),
  })

  // Build person-based rows from calendar items
  const personRows = useMemo<PersonRow[]>(() => {
    const items = calendarData?.items || []
    const byPerson = new Map<string, PersonRow>()
    const unassigned: GanttTask[] = []

    for (const item of items) {
      if (searchQuery && item.title && !item.title.toLowerCase().includes(searchQuery.toLowerCase())) continue

      const start = item.start_date ? parseISO(item.start_date) : (item.due_date ? parseISO(item.due_date) : dateRange.start)
      const end = item.end_date ? parseISO(item.end_date) : (item.due_date ? parseISO(item.due_date) : start)
      const stages: GanttStage[] = (item.stages || []).map((s: any) => ({
        id: s.id,
        name: s.stage_name || s.name || '',
        start: s.due_date ? addDays(parseISO(s.due_date), -1) : start,
        end: s.due_date ? parseISO(s.due_date) : end,
        color: s.status_color || 'green',
        status: s.status || 'pending',
      }))

      const gTask: GanttTask = {
        id: item.id,
        title: item.title || '',
        type: item.type_task || item.type || '',
        status: item.status || '',
        priority: item.priority || '',
        start,
        end,
        stages,
        assignees: (item.assignments || []).map((a: any) => a.user_id),
        assigneeNames: (item.assignments || []).map((a: any) => a.user_name || a.user_id?.slice(0, 8) || '?'),
        description: item.description,
      }

      if (!item.assignments || item.assignments.length === 0) {
        unassigned.push(gTask)
      } else {
        for (const a of item.assignments) {
          const key = a.user_id || 'unknown'
          if (!byPerson.has(key)) {
            byPerson.set(key, { userId: key, name: a.user_name || key.slice(0, 8), role: item.type_task || item.type || '', tasks: [] })
          }
          byPerson.get(key)!.tasks.push(gTask)
        }
      }
    }

    const rows = Array.from(byPerson.values())
    if (unassigned.length > 0) {
      rows.push({ userId: '__unassigned__', name: 'Не назначено', role: '', tasks: unassigned })
    }

    // Filter "my only"
    if (showMyOnly && user?.id) {
      return rows.filter(r => r.userId === user.id)
    }

    return rows
  }, [calendarData, searchQuery, showMyOnly, user, dateRange])

  // dayWidth зависит ТОЛЬКО от режима просмотра (сколько дней нужно вместить)
  const dayWidth = viewMode === 'semester' ? 18 : viewMode === 'month' ? 36 : 80
  // rowHeight зависит от детализации (сколько информации показывать)
  const rowHeight = detailLevel === 'compact' ? 28 : detailLevel === 'detailed' ? 72 : 40

  const getBarStyle = useCallback((task: GanttTask) => {
    const totalDays = dateRange.days.length
    const startOff = Math.max(0, differenceInDays(task.start, dateRange.start))
    const endOff = Math.min(totalDays, differenceInDays(task.end, dateRange.start) + 1)
    const dur = Math.max(1, endOff - startOff)
    const w = dur * dayWidth
    return {
      left: startOff * dayWidth,
      width: Math.max(w, dayWidth * 2),
    }
  }, [dateRange, dayWidth])

  const getStageBarStyle = useCallback((stage: GanttStage) => {
    const totalDays = dateRange.days.length
    const startOff = Math.max(0, differenceInDays(stage.start, dateRange.start))
    const endOff = Math.min(totalDays, differenceInDays(stage.end, dateRange.start) + 1)
    const dur = Math.max(1, endOff - startOff)
    const w = dur * dayWidth
    return {
      left: startOff * dayWidth,
      width: Math.max(w, dayWidth * 1.5),
    }
  }, [dateRange, dayWidth])

  const navigateDate = (direction: 'prev' | 'next') => {
    const d = new Date(currentDate)
    if (viewMode === 'week') d.setDate(d.getDate() + (direction === 'next' ? 7 : -7))
    else if (viewMode === 'month') d.setMonth(d.getMonth() + (direction === 'next' ? 1 : -1))
    else d.setMonth(d.getMonth() + (direction === 'next' ? 6 : -6))
    setCurrentDate(d)
  }

  const handleTaskHover = (e: React.MouseEvent, task: GanttTask) => {
    const rect = e.currentTarget.getBoundingClientRect()
    setHoverPosition({ x: Math.min(rect.left, window.innerWidth - 320), y: Math.min(rect.bottom + 8, window.innerHeight - 250) })
    setHoveredTask(task)
  }

  const handleTaskClick = (task: GanttTask) => {
    setSelectedTask(task)
  }

  const todayOffset = differenceInDays(new Date(), dateRange.start)
  const totalWidth = dateRange.days.length * dayWidth

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col p-4 space-y-3">
      {/* Header */}
      <div className={`glass-enhanced ${theme} p-3 rounded-xl flex flex-col xl:flex-row justify-between items-start xl:items-center gap-3`}>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 w-full xl:w-auto">
          <div className="flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-best-accent" />
            <h1 className="text-xl font-bold text-white">Таймлайн</h1>
            <span className="text-white/40 text-xs">{format(currentDate, 'LLLL yyyy', { locale: ru })}</span>
          </div>
          <div className="flex bg-white/10 rounded-lg p-0.5">
            {(['week', 'month', 'semester'] as const).map(m => (
              <button key={m} onClick={() => setViewMode(m)}
                className={`px-3 py-1 rounded-md text-xs transition-all ${viewMode === m ? 'bg-best-primary text-white' : 'text-white/60 hover:text-white'}`}
              >{m === 'week' ? 'Неделя' : m === 'month' ? 'Месяц' : 'Семестр'}</button>
            ))}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 w-full xl:w-auto">
          <div className="relative flex-1 min-w-[150px] max-w-[220px]">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-white/40" />
            <input type="text" placeholder="Поиск..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-white placeholder-white/30 focus:outline-none focus:border-best-primary/50 text-xs" />
          </div>
          <select value={selectedRole} onChange={e => setSelectedRole(e.target.value as any)}
            className={`bg-white/10 text-white rounded-lg px-2 py-1.5 border border-white/20 text-xs [&>option]:bg-gray-800`}>
            <option value="all">Все</option>
            <option value="smm">SMM</option>
            <option value="design">Design</option>
            <option value="channel">Channel</option>
            <option value="prfr">PR-FR</option>
          </select>
          <select value={detailLevel} onChange={e => setDetailLevel(e.target.value as any)}
            className={`bg-white/10 text-white rounded-lg px-2 py-1.5 border border-white/20 text-xs [&>option]:bg-gray-800`}>
            <option value="compact">Компактно</option>
            <option value="normal">Обычно</option>
            <option value="detailed">Подробно</option>
          </select>
          <button onClick={() => setShowMyOnly(!showMyOnly)}
            className={`flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs transition-all border ${showMyOnly ? 'bg-best-primary text-white border-best-primary' : 'bg-white/5 text-white/60 border-white/10 hover:text-white'}`}>
            {showMyOnly ? <UserIcon className="h-3 w-3" /> : <Users className="h-3 w-3" />}
            <span>{showMyOnly ? 'Мои' : 'Все'}</span>
          </button>
          <div className="flex items-center gap-0.5">
            <button onClick={() => navigateDate('prev')} className="p-1.5 hover:bg-white/10 rounded text-white"><ChevronLeft className="h-4 w-4" /></button>
            <button onClick={() => setCurrentDate(new Date())} className="px-2 py-1 hover:bg-white/10 rounded text-white text-xs">Сегодня</button>
            <button onClick={() => navigateDate('next')} className="p-1.5 hover:bg-white/10 rounded text-white"><ChevronRight className="h-4 w-4" /></button>
          </div>
          {isCoordinator && (
            <button onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}
              className="p-1.5 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 disabled:opacity-50" title="Синхронизировать">
              {syncMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 px-1 flex-wrap">
        {Object.entries(stageLabelMap).map(([color, label]) => (
          <div key={color} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded-sm ${stageColorMap[color]}`} />
            <span className="text-white/50 text-[10px]">{label}</span>
          </div>
        ))}
      </div>

      {/* Gantt Chart */}
      <div className={`glass-enhanced ${theme} flex-1 rounded-xl overflow-hidden relative border border-white/10`}>
        {isLoading ? (
          <div className="flex items-center justify-center h-full"><Loader2 className="h-8 w-8 animate-spin text-best-primary" /></div>
        ) : (
          <div className="absolute inset-0 overflow-auto" ref={scrollContainerRef}>
            <div style={{ minWidth: totalWidth + 180 }}>
              {/* Month headers */}
              {viewMode !== 'week' && (
                <div className="sticky top-0 z-30 flex" style={{ height: 24 }}>
                  <div className="sticky left-0 z-40 w-[180px] flex-shrink-0 bg-[#1a1a2e]" />
                  <div className="flex">
                    {monthHeaders.map((mh, i) => (
                      <div key={i} style={{ width: mh.span * dayWidth }} className="text-center text-[10px] text-white/60 font-semibold border-r border-white/10 bg-[#1a1a2e] capitalize leading-6">
                        {mh.label}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Day headers */}
              <div className={`sticky ${viewMode !== 'week' ? 'top-6' : 'top-0'} z-20 flex border-b border-white/10`}>
                <div className="sticky left-0 z-40 w-[180px] flex-shrink-0 p-2 border-r border-white/10 bg-[#1a1a2e]">
                  <span className="text-white/70 font-semibold text-xs">Исполнитель</span>
                </div>
                <div className="flex">
                  {dateRange.days.map(day => {
                    const isToday = isSameDay(day, new Date())
                    const isWeekend = day.getDay() === 0 || day.getDay() === 6
                    return (
                      <div key={day.toISOString()} style={{ width: dayWidth, minWidth: dayWidth }}
                        className={`text-center border-r border-white/5 py-1 flex flex-col items-center ${isToday ? 'bg-best-primary/20' : isWeekend ? 'bg-white/[0.03]' : 'bg-[#1a1a2e]'}`}>
                        {viewMode !== 'semester' && <span className="text-[9px] text-white/40 uppercase">{format(day, 'EEEEEE', { locale: ru })}</span>}
                        <span className={`text-[11px] font-bold ${isToday ? 'text-best-primary' : 'text-white/80'}`}>{format(day, 'd')}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Person rows */}
              {personRows.map(row => (
                <div key={row.userId}>
                  {row.tasks.map((task, ti) => (
                    <div key={`${row.userId}-${task.id}-${ti}`} className="flex border-b border-white/5 hover:bg-white/[0.02] transition-colors" style={{ height: rowHeight }}>
                      <div className="sticky left-0 z-10 w-[180px] flex-shrink-0 px-3 flex items-center border-r border-white/10 bg-[#1a1a2e] hover:bg-[#252540] transition-colors">
                        {ti === 0 ? (
                          <div className="truncate">
                            <span className="text-white text-xs font-medium block truncate">{row.name}</span>
                            {row.role && <span className="text-white/30 text-[9px] uppercase">{row.role}</span>}
                          </div>
                        ) : null}
                      </div>
                      <div className="relative flex-1" style={{ width: totalWidth }}>
                        {/* Day grid background */}
                        <div className="absolute inset-0 flex pointer-events-none">
                          {dateRange.days.map(day => (
                            <div key={day.toISOString()} style={{ width: dayWidth, minWidth: dayWidth }}
                              className={`border-r border-white/5 ${isSameDay(day, new Date()) ? 'bg-best-primary/5' : ''}`} />
                          ))}
                        </div>

                        {/* Task bar */}
                        {detailLevel === 'detailed' && task.stages.length > 0 ? (
                          <>
                            {/* Подробно: общий бар + этапы внутри */}
                            {(() => {
                              const style = getBarStyle(task)
                              const typeColor = task.status === 'completed' ? 'bg-green-500/20 border-green-400/30'
                                : task.type === 'smm' ? 'bg-emerald-500/10 border-emerald-400/30'
                                : task.type === 'design' ? 'bg-blue-500/10 border-blue-400/30'
                                : task.type === 'channel' ? 'bg-orange-500/10 border-orange-400/30'
                                : task.type === 'prfr' ? 'bg-purple-500/10 border-purple-400/30'
                                : 'bg-gray-500/10 border-gray-400/30'
                              return (
                                <div
                                  className={`absolute top-1 rounded border ${typeColor}`}
                                  style={{ left: style.left, width: style.width, height: rowHeight - 8 }}
                                  onClick={() => handleTaskClick(task)}
                                  onMouseEnter={e => handleTaskHover(e, task)}
                                  onMouseLeave={() => { setHoveredTask(null); setHoverPosition(null) }}
                                >
                                  <span className="text-[9px] text-white/80 font-semibold px-1 truncate block drop-shadow">{task.title}</span>
                                  <div className="flex items-end gap-px px-0.5 absolute bottom-0.5 left-0 right-0" style={{ height: rowHeight - 24 }}>
                                    {task.stages.map(stage => {
                                      const ss = getStageBarStyle(stage)
                                      const relLeft = ss.left - style.left
                                      return (
                                        <div key={stage.id}
                                          className={`absolute rounded-sm ${stageColorMap[stage.color]} cursor-pointer hover:brightness-125`}
                                          style={{ left: Math.max(0, relLeft), width: Math.max(ss.width, dayWidth), height: '60%', bottom: 0 }}
                                          title={`${stage.name} — ${format(stage.end, 'd.MM')}`}
                                        >
                                          <span className="text-[7px] text-white/90 px-0.5 truncate block leading-tight">{stage.name}</span>
                                        </div>
                                      )
                                    })}
                                  </div>
                                </div>
                              )
                            })()}
                          </>
                        ) : (() => {
                            const style = getBarStyle(task)
                            const typeColor = task.status === 'completed' ? 'bg-green-500/60 border-green-400/50'
                              : task.status === 'cancelled' ? 'bg-red-500/30 border-red-400/30'
                              : task.type === 'smm' ? 'bg-emerald-500/50 border-emerald-400/50'
                              : task.type === 'design' ? 'bg-blue-500/50 border-blue-400/50'
                              : task.type === 'channel' ? 'bg-orange-500/50 border-orange-400/50'
                              : task.type === 'prfr' ? 'bg-purple-500/50 border-purple-400/50'
                              : 'bg-gray-500/50 border-gray-400/50'
                            return (
                              <div
                                className={`absolute top-1 rounded cursor-pointer hover:brightness-125 transition-all border ${typeColor}`}
                                style={{ left: style.left, width: style.width, height: rowHeight - 8 }}
                                onClick={() => handleTaskClick(task)}
                                onMouseEnter={e => handleTaskHover(e, task)}
                                onMouseLeave={() => { setHoveredTask(null); setHoverPosition(null) }}>
                                {detailLevel !== 'compact' && (
                                  <span className="text-[10px] text-white font-semibold px-1.5 truncate block leading-tight mt-1 drop-shadow-md">{task.title}</span>
                                )}
                              </div>
                            )
                          })()}
                      </div>
                    </div>
                  ))}
                </div>
              ))}

              {personRows.length === 0 && (
                <div className="p-8 text-center text-white/40 text-sm sticky left-0">
                  {showMyOnly ? 'У вас нет задач в этом периоде' : 'Нет задач в выбранном периоде'}
                </div>
              )}
            </div>

            {/* Today marker line */}
            {todayOffset >= 0 && todayOffset < dateRange.days.length && (
              <div className="absolute top-0 bottom-0 pointer-events-none z-10"
                style={{ left: 180 + todayOffset * dayWidth + dayWidth / 2, width: 2 }}>
                <div className="w-full h-full bg-best-primary/60" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hover card */}
      {hoveredTask && hoverPosition && !selectedTask && (
        <div className={`fixed z-50 w-80 p-3 rounded-xl glass-enhanced ${theme} border border-white/20 shadow-2xl pointer-events-none`}
          style={{ left: hoverPosition.x, top: hoverPosition.y }}>
          <div className="flex items-start justify-between mb-2">
            <h4 className="text-white font-bold text-sm flex-1">{hoveredTask.title}</h4>
            <span className="text-[10px] uppercase font-bold text-white/60 ml-2">{hoveredTask.status}</span>
          </div>
          {hoveredTask.description && <p className="text-white/50 text-xs mb-2 line-clamp-2">{hoveredTask.description}</p>}
          <div className="flex items-center gap-2 text-xs text-white/60 mb-2">
            <CalendarIcon className="h-3 w-3" />
            <span>{format(hoveredTask.start, 'd MMM', { locale: ru })} — {format(hoveredTask.end, 'd MMM', { locale: ru })}</span>
          </div>
          {hoveredTask.assigneeNames?.length > 0 && (
            <div className="text-xs text-white/50">
              <UserIcon className="h-3 w-3 inline mr-1" />{hoveredTask.assigneeNames.join(', ')}
            </div>
          )}
          {hoveredTask.stages?.length > 0 && (
            <div className="mt-2 pt-2 border-t border-white/10 space-y-1">
              {hoveredTask.stages.map((s: GanttStage) => (
                <div key={s.id} className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-sm ${stageColorMap[s.color]}`} />
                  <span className="text-white/60 text-[10px]">{s.name}</span>
                  {s.end && <span className="text-white/30 text-[10px] ml-auto">{format(s.end, 'd.MM')}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Task detail panel (slide-over) */}
      {selectedTask && (
        <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setSelectedTask(null)}>
          <div className="absolute inset-0 bg-black/40" />
          <div className={`relative w-full max-w-md glass-enhanced ${theme} border-l border-white/20 p-6 overflow-y-auto`}
            onClick={e => e.stopPropagation()}>
            <button onClick={() => setSelectedTask(null)} className="absolute top-4 right-4 text-white/60 hover:text-white">
              <X className="h-5 w-5" />
            </button>
            <h2 className="text-xl font-bold text-white mb-2">{selectedTask.title}</h2>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs px-2 py-0.5 rounded bg-best-primary/20 text-best-primary uppercase">{selectedTask.type}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-white/60">{selectedTask.status}</span>
              <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-white/60">{selectedTask.priority}</span>
            </div>
            {selectedTask.description && <p className="text-white/60 text-sm mb-4">{selectedTask.description}</p>}
            <div className="text-sm text-white/70 mb-4">
              <CalendarIcon className="h-4 w-4 inline mr-1" />
              {format(selectedTask.start, 'd MMMM yyyy', { locale: ru })} — {format(selectedTask.end, 'd MMMM yyyy', { locale: ru })}
            </div>
            {selectedTask.assigneeNames?.length > 0 && (
              <div className="mb-4">
                <h3 className="text-white/80 font-semibold text-sm mb-1">Исполнители:</h3>
                {selectedTask.assigneeNames.map((name: string, i: number) => (
                  <span key={i} className="inline-block text-xs bg-white/10 text-white/70 rounded px-2 py-0.5 mr-1 mb-1">{name}</span>
                ))}
              </div>
            )}
            {selectedTask.stages?.length > 0 && (
              <div className="mb-4">
                <h3 className="text-white/80 font-semibold text-sm mb-2">Этапы:</h3>
                <div className="space-y-2">
                  {selectedTask.stages.map((s: GanttStage) => (
                    <div key={s.id} className={`p-2 rounded border ${stageColorBorder[s.color]} bg-white/5`}>
                      <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-sm ${stageColorMap[s.color]}`} />
                        <span className="text-white text-sm font-medium">{s.name}</span>
                        <span className="text-white/40 text-xs ml-auto">{stageLabelMap[s.color]}</span>
                      </div>
                      <div className="text-white/50 text-xs mt-1">
                        {format(s.start, 'd MMM', { locale: ru })} — {format(s.end, 'd MMM', { locale: ru })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <button onClick={() => { setSelectedTask(null); navigate(`/tasks?highlight=${selectedTask.id}`) }}
              className="w-full bg-best-primary text-white py-2 rounded-lg hover:bg-best-primary/80 text-sm font-medium mt-2">
              Открыть задачу
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
