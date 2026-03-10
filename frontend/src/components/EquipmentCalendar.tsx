import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { equipmentApi, type Equipment, type TimelineDayRequest } from '../services/equipment'
import { useThemeStore } from '../store/themeStore'

const WEEKDAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const MONTH_NAMES = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
]

function getWeekdayIndex(dateStr: string): number {
  const d = new Date(dateStr)
  return (d.getDay() + 6) % 7
}

interface Props {
  equipmentList: Equipment[]
}

export default function EquipmentCalendar({ equipmentList }: Props) {
  const { theme } = useThemeStore()
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [hoveredCell, setHoveredCell] = useState<{ eqId: string; day: number } | null>(null)

  const { data: timeline, isLoading } = useQuery({
    queryKey: ['equipment', 'timeline', month, year],
    queryFn: () => equipmentApi.getTimeline(month, year),
  })

  const prevMonth = () => {
    if (month === 1) { setMonth(12); setYear(y => y - 1) }
    else setMonth(m => m - 1)
  }
  const nextMonth = () => {
    if (month === 12) { setMonth(1); setYear(y => y + 1) }
    else setMonth(m => m + 1)
  }

  const daysInMonth = new Date(year, month, 0).getDate()

  const calendarData = useMemo(() => {
    if (!timeline?.timeline || !equipmentList.length) return null

    const requestsByEquipmentAndDay: Record<string, Record<number, TimelineDayRequest[]>> = {}

    for (const eq of equipmentList) {
      requestsByEquipmentAndDay[eq.id] = {}
    }

    for (const dayData of timeline.timeline) {
      const dayNum = new Date(dayData.date).getDate()
      for (const req of dayData.requests) {
        if (!requestsByEquipmentAndDay[req.equipment_id]) {
          requestsByEquipmentAndDay[req.equipment_id] = {}
        }
        if (!requestsByEquipmentAndDay[req.equipment_id][dayNum]) {
          requestsByEquipmentAndDay[req.equipment_id][dayNum] = []
        }
        requestsByEquipmentAndDay[req.equipment_id][dayNum].push(req)
      }
    }

    return requestsByEquipmentAndDay
  }, [timeline, equipmentList])

  const getCellColor = (requests: TimelineDayRequest[] | undefined) => {
    if (!requests || requests.length === 0) return ''
    const hasApproved = requests.some(r => r.status === 'approved' || r.status === 'active')
    const hasPending = requests.some(r => r.status === 'pending')
    const hasCompleted = requests.every(r => r.status === 'completed' || r.status === 'cancelled')
    if (hasCompleted) return 'bg-white/10'
    if (hasApproved) return 'bg-red-500/40 border-red-500/60'
    if (hasPending) return 'bg-yellow-500/40 border-yellow-500/60'
    return 'bg-white/10'
  }

  const getCellTooltip = (requests: TimelineDayRequest[] | undefined) => {
    if (!requests || requests.length === 0) return ''
    return requests.map(r => {
      const statusMap: Record<string, string> = {
        pending: 'На рассмотрении',
        approved: 'Одобрено',
        active: 'Выдано',
        completed: 'Возвращено',
        rejected: 'Отклонено',
        cancelled: 'Отменено',
      }
      return `#${r.request_id.slice(0, 4)} ${r.user_name} — ${statusMap[r.status] || r.status}`
    }).join('\n')
  }

  return (
    <div className={`glass-enhanced ${theme} rounded-xl p-4 md:p-6 mt-6 overflow-x-auto`}>
      <div className="flex items-center justify-between mb-4">
        <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h3 className={`text-lg font-bold text-white text-readable ${theme}`}>
          {MONTH_NAMES[month - 1]} {year}
        </h3>
        <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-white/10 transition-colors text-white">
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-best-primary" />
        </div>
      )}

      {!isLoading && calendarData && (
        <div className="min-w-[700px]">
          {/* Header: days */}
          <div className="flex">
            <div className="w-40 flex-shrink-0 p-1 text-white/50 text-xs font-medium border-b border-white/10">
              Оборудование
            </div>
            {Array.from({ length: daysInMonth }, (_, i) => {
              const dayNum = i + 1
              const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(dayNum).padStart(2, '0')}`
              const wdi = getWeekdayIndex(dateStr)
              const isWeekend = wdi >= 5
              const isToday = dayNum === now.getDate() && month === now.getMonth() + 1 && year === now.getFullYear()
              return (
                <div
                  key={dayNum}
                  className={`flex-1 min-w-[28px] text-center border-b border-white/10 p-0.5 ${isWeekend ? 'bg-white/5' : ''}`}
                >
                  <div className="text-[9px] text-white/40">{WEEKDAY_NAMES[wdi]}</div>
                  <div className={`text-xs font-medium ${isToday ? 'text-best-primary font-bold' : 'text-white/70'}`}>
                    {dayNum}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Equipment rows */}
          {equipmentList.map(eq => (
            <div key={eq.id} className="flex hover:bg-white/5 transition-colors">
              <div className="w-40 flex-shrink-0 p-1.5 text-white text-[11px] font-medium truncate border-b border-white/5" title={eq.name}>
                {eq.name}
              </div>
              {Array.from({ length: daysInMonth }, (_, i) => {
                const dayNum = i + 1
                const reqs = calendarData[eq.id]?.[dayNum]
                const cellColor = getCellColor(reqs)
                const isHovered = hoveredCell?.eqId === eq.id && hoveredCell?.day === dayNum
                return (
                  <div
                    key={dayNum}
                    className={`flex-1 min-w-[28px] h-7 border-b border-r border-white/5 relative cursor-default ${cellColor} ${isHovered ? 'ring-1 ring-white/50' : ''}`}
                    onMouseEnter={() => setHoveredCell({ eqId: eq.id, day: dayNum })}
                    onMouseLeave={() => setHoveredCell(null)}
                    title={getCellTooltip(reqs)}
                  >
                    {reqs && reqs.length > 0 && (
                      <span className="absolute inset-0 flex items-center justify-center text-[8px] text-white/80 font-bold">
                        {reqs.length}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          ))}

          {/* Legend */}
          <div className="flex items-center gap-4 mt-3 text-xs text-white/60">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-yellow-500/40 border border-yellow-500/60" />
              <span>На рассмотрении</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-red-500/40 border border-red-500/60" />
              <span>Одобрено / Выдано</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded bg-white/10 border border-white/20" />
              <span>Возвращено</span>
            </div>
          </div>
        </div>
      )}

      {!isLoading && timeline && timeline.total_requests === 0 && (
        <p className="text-white/40 text-center py-6 text-sm">
          Нет заявок в этом месяце
        </p>
      )}
    </div>
  )
}
