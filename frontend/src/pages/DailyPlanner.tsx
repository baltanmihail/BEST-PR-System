import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  Trash2,
  ChevronLeft,
  ChevronRight,
  Users,
  User as UserIcon,
  Loader2,
  Send,
  Circle,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import {
  dailyTasksApi,
  type DailyTask,
  type DailyTaskCreate,
  type DailyTaskUpdate,
} from '../services/dailyTasks'
import { usersApi } from '../services/users'
import { isCoordinatorOrAbove } from '../types/user'
import { format, addDays, subDays, isToday } from 'date-fns'
import { ru } from 'date-fns/locale'

function nextPriority(p: number): number {
  return p >= 2 ? 0 : p + 1
}

function formatScheduledDisplay(t: string | null | undefined): string {
  if (t == null || t === '') return ''
  const m = /^(\d{1,2}):(\d{2})/.exec(String(t))
  if (m) {
    const h = m[1].padStart(2, '0')
    return `${h}:${m[2]}`
  }
  return String(t).slice(0, 5)
}

function scheduledTimeSortKey(t: string | null | undefined): string | null {
  if (t == null || String(t).trim() === '') return null
  const m = /^(\d{1,2}):(\d{2})(?::(\d{2}))?/.exec(String(t))
  if (m) {
    const sec = (m[3] ?? '00').padStart(2, '0')
    return `${m[1].padStart(2, '0')}:${m[2]}:${sec}`
  }
  return String(t)
}

function compareTasks(a: DailyTask, b: DailyTask): number {
  const ka = scheduledTimeSortKey(a.scheduled_time)
  const kb = scheduledTimeSortKey(b.scheduled_time)
  if (ka != null && kb != null) {
    const tcmp = ka.localeCompare(kb)
    if (tcmp !== 0) return tcmp
  } else if (ka != null && kb == null) return -1
  else if (ka == null && kb != null) return 1

  const pa = a.priority ?? 0
  const pb = b.priority ?? 0
  if (pb !== pa) return pb - pa

  const da = a.created_at ?? ''
  const db = b.created_at ?? ''
  if (da !== db) return da.localeCompare(db)
  return a.id.localeCompare(b.id)
}

function sortTaskList(list: DailyTask[]): DailyTask[] {
  return [...list].sort(compareTasks)
}

export default function DailyPlanner() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

  const [selectedDate, setSelectedDate] = useState(new Date())
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskTime, setNewTaskTime] = useState('')
  const [newTaskPriority, setNewTaskPriority] = useState(0)
  const [showAllUsers, setShowAllUsers] = useState(false)
  const [assigneeId, setAssigneeId] = useState<string | undefined>(undefined)
  const [showAssigneeDropdown, setShowAssigneeDropdown] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const dateStr = format(selectedDate, 'yyyy-MM-dd')
  const isCoordinator = user && isCoordinatorOrAbove(user.role)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowAssigneeDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const { data: tasks = [], isLoading } = useQuery({
    queryKey: ['daily-tasks', dateStr, showAllUsers ? 'all' : user?.id],
    queryFn: () => {
      if (showAllUsers && isCoordinator) {
        return dailyTasksApi.getTasks({ target_date: dateStr })
      }
      return dailyTasksApi.getMyTasks(dateStr)
    },
    enabled: !!user,
  })

  const { data: stats } = useQuery({
    queryKey: ['daily-tasks-stats', dateStr],
    queryFn: () => dailyTasksApi.getStats(dateStr),
    enabled: !!user,
  })

  const { data: usersData } = useQuery({
    queryKey: ['users-active'],
    queryFn: () => usersApi.getUsers({ is_active: true, limit: 100 }),
    enabled: isCoordinator === true,
  })

  const activeUsers = useMemo(() => usersData?.items || [], [usersData])

  const invalidateTasks = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['daily-tasks'] })
    queryClient.invalidateQueries({ queryKey: ['daily-tasks-stats'] })
  }, [queryClient])

  const createMutation = useMutation({
    mutationFn: (data: DailyTaskCreate) => dailyTasksApi.create(data),
    onSuccess: () => {
      invalidateTasks()
      setNewTaskTitle('')
      setNewTaskTime('')
      setNewTaskPriority(0)
      setAssigneeId(undefined)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_done }: { id: string; is_done: boolean }) =>
      dailyTasksApi.update(id, { is_done }),
    onSuccess: invalidateTasks,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => dailyTasksApi.delete(id),
    onSuccess: invalidateTasks,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: DailyTaskUpdate }) =>
      dailyTasksApi.update(id, data),
    onSuccess: invalidateTasks,
  })

  const handleCreate = () => {
    const title = newTaskTitle.trim()
    if (!title) return
    const payload: DailyTaskCreate = {
      title,
      date: dateStr,
      priority: newTaskPriority,
      assignee_id: assigneeId || undefined,
    }
    if (newTaskTime) payload.scheduled_time = newTaskTime
    createMutation.mutate(payload)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleCreate()
    }
  }

  const pendingTasks = useMemo(
    () => sortTaskList(tasks.filter(t => !t.is_done)),
    [tasks],
  )
  const doneTasks = useMemo(
    () => sortTaskList(tasks.filter(t => t.is_done)),
    [tasks],
  )

  const selectedAssignee = activeUsers.find(u => u.id === assigneeId)
  const progressPct = stats
    ? stats.total > 0
      ? Math.round((stats.done / stats.total) * 100)
      : 0
    : 0

  const updatingTaskId =
    updateMutation.isPending && updateMutation.variables
      ? updateMutation.variables.id
      : undefined

  const priorityDotClass = (p: number) => {
    if (p >= 2) return 'fill-red-500 text-red-500'
    if (p === 1) return 'fill-orange-400 text-orange-400'
    return 'fill-white/25 text-white/25'
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Планёрка</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSelectedDate(d => subDays(d, 1))}
            className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            type="button"
            onClick={() => setSelectedDate(new Date())}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
              isToday(selectedDate)
                ? 'bg-blue-500/30 text-blue-300 border border-blue-500/40'
                : 'bg-white/10 text-white/70 hover:bg-white/15 hover:text-white'
            }`}
          >
            {isToday(selectedDate) ? 'Сегодня' : format(selectedDate, 'd MMM', { locale: ru })}
          </button>
          <button
            type="button"
            onClick={() => setSelectedDate(d => addDays(d, 1))}
            className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      <p className="text-white/50 text-sm -mt-2">
        {format(selectedDate, 'EEEE, d MMMM yyyy', { locale: ru })}
      </p>

      {stats && stats.total > 0 && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-sm text-white/60">
            <span>
              Выполнено {stats.done} из {stats.total}
            </span>
            <span>{progressPct}%</span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{
                width: `${progressPct}%`,
                background:
                  progressPct === 100
                    ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                    : 'linear-gradient(90deg, #3b82f6, #6366f1)',
              }}
            />
          </div>
        </div>
      )}

      {isCoordinator && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setShowAllUsers(false)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${
              !showAllUsers
                ? 'bg-blue-500/30 text-blue-300 border border-blue-500/40'
                : 'bg-white/10 text-white/60 hover:text-white'
            }`}
          >
            <UserIcon className="w-4 h-4" /> Мои
          </button>
          <button
            type="button"
            onClick={() => setShowAllUsers(true)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${
              showAllUsers
                ? 'bg-blue-500/30 text-blue-300 border border-blue-500/40'
                : 'bg-white/10 text-white/60 hover:text-white'
            }`}
          >
            <Users className="w-4 h-4" /> Все
          </button>
        </div>
      )}

      <div className="rounded-xl border border-white/15 bg-white/5 backdrop-blur-sm p-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={inputRef}
            value={newTaskTitle}
            onChange={e => setNewTaskTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Новая задача..."
            className="min-w-[12rem] flex-1 bg-white/10 border border-white/15 rounded-lg px-3 py-2.5 text-white placeholder-white/40 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 transition text-sm"
          />
          <input
            type="time"
            value={newTaskTime}
            onChange={e => setNewTaskTime(e.target.value)}
            className="w-[7.25rem] shrink-0 bg-white/10 border border-white/15 rounded-lg px-2 py-2 text-white text-sm [color-scheme:dark] focus:outline-none focus:border-blue-500/50"
          />
          <button
            type="button"
            onClick={() => setNewTaskPriority(nextPriority(newTaskPriority))}
            title="Приоритет"
            className="shrink-0 p-2 rounded-lg border border-white/15 bg-white/10 hover:bg-white/15 transition flex items-center justify-center"
          >
            <Circle
              className={`w-4 h-4 ${priorityDotClass(newTaskPriority)}`}
              strokeWidth={2}
            />
          </button>
          {isCoordinator && (
            <div className="relative shrink-0" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setShowAssigneeDropdown(!showAssigneeDropdown)}
                className="flex items-center gap-1.5 px-2.5 py-2 rounded-lg text-xs text-white/70 hover:text-white border border-white/15 bg-white/10 hover:bg-white/15 transition max-w-[9rem] truncate"
              >
                <UserIcon className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">
                  {selectedAssignee ? selectedAssignee.full_name : 'Себе'}
                </span>
              </button>
              {showAssigneeDropdown && (
                <div className="absolute bottom-full mb-1 left-0 z-50 w-56 max-h-48 overflow-y-auto bg-gray-900/95 backdrop-blur-md border border-white/20 rounded-lg shadow-xl">
                  <button
                    type="button"
                    onClick={() => {
                      setAssigneeId(undefined)
                      setShowAssigneeDropdown(false)
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-white/80 hover:bg-white/10 transition"
                  >
                    Себе
                  </button>
                  {activeUsers.map(u => (
                    <button
                      key={u.id}
                      type="button"
                      onClick={() => {
                        setAssigneeId(u.id)
                        setShowAssigneeDropdown(false)
                      }}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-white/10 transition ${
                        assigneeId === u.id ? 'text-blue-300 bg-blue-500/10' : 'text-white/80'
                      }`}
                    >
                      {u.full_name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <button
            type="button"
            onClick={handleCreate}
            disabled={!newTaskTitle.trim() || createMutation.isPending}
            className="shrink-0 p-2.5 rounded-lg bg-blue-500/30 text-blue-300 hover:bg-blue-500/40 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {createMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <Loader2 className="w-6 h-6 animate-spin text-white/40" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-12 text-white/40">
          <p className="text-lg">Нет задач на этот день</p>
          <p className="text-sm mt-1">Создай первую задачу выше</p>
        </div>
      ) : (
        <div className="space-y-2">
          {pendingTasks.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              showAssignee={showAllUsers}
              onToggle={() => toggleMutation.mutate({ id: task.id, is_done: true })}
              onDelete={() => deleteMutation.mutate(task.id)}
              onUpdateTitle={title =>
                updateMutation.mutate({ id: task.id, data: { title } })
              }
              onUpdatePriority={priority =>
                updateMutation.mutate({ id: task.id, data: { priority } })
              }
              isBusy={updatingTaskId === task.id}
            />
          ))}

          {doneTasks.length > 0 && pendingTasks.length > 0 && (
            <div className="flex items-center gap-3 py-2">
              <div className="flex-1 h-px bg-white/10" />
              <span className="text-xs text-white/30">Выполнено ({doneTasks.length})</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
          )}

          {doneTasks.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              showAssignee={showAllUsers}
              onToggle={() => toggleMutation.mutate({ id: task.id, is_done: false })}
              onDelete={() => deleteMutation.mutate(task.id)}
              onUpdateTitle={title =>
                updateMutation.mutate({ id: task.id, data: { title } })
              }
              onUpdatePriority={priority =>
                updateMutation.mutate({ id: task.id, data: { priority } })
              }
              isBusy={updatingTaskId === task.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TaskItem({
  task,
  showAssignee,
  onToggle,
  onDelete,
  onUpdateTitle,
  onUpdatePriority,
  isBusy,
}: {
  task: DailyTask
  showAssignee: boolean
  onToggle: () => void
  onDelete: () => void
  onUpdateTitle: (title: string) => void
  onUpdatePriority: (priority: number) => void
  isBusy: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(task.title)
  const editInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!editing) setDraft(task.title)
  }, [task.title, editing])

  useEffect(() => {
    if (editing) {
      editInputRef.current?.focus()
      editInputRef.current?.select()
    }
  }, [editing])

  const p = task.priority ?? 0
  const timeLabel = formatScheduledDisplay(task.scheduled_time)
  const hasTime = timeLabel !== ''

  const dotClass =
    p >= 2 ? 'fill-red-500 text-red-500' : p === 1 ? 'fill-orange-400 text-orange-400' : 'fill-white/20 text-white/30'

  const commitEdit = () => {
    const t = draft.trim()
    if (!t) {
      setDraft(task.title)
      setEditing(false)
      return
    }
    if (t !== task.title) onUpdateTitle(t)
    setEditing(false)
  }

  const cancelEdit = () => {
    setDraft(task.title)
    setEditing(false)
  }

  return (
    <div
      className={`group flex items-center gap-2.5 px-3 py-2.5 rounded-xl transition-all ${
        task.is_done ? 'bg-white/5 opacity-60' : 'bg-white/10 hover:bg-white/15'
      }`}
    >
      <button
        type="button"
        onClick={e => {
          e.stopPropagation()
          onUpdatePriority(nextPriority(p))
        }}
        disabled={isBusy}
        className="flex-shrink-0 p-0.5 rounded-md hover:bg-white/10 transition disabled:opacity-50"
        aria-label="Приоритет"
      >
        <Circle className={`w-3.5 h-3.5 ${dotClass}`} strokeWidth={2} />
      </button>

      <button
        type="button"
        onClick={onToggle}
        className={`flex-shrink-0 w-6 h-6 rounded-lg border-2 flex items-center justify-center transition-all ${
          task.is_done
            ? 'bg-green-500/30 border-green-500/60 text-green-400'
            : 'border-white/30 hover:border-blue-400 hover:bg-blue-500/10'
        }`}
      >
        {task.is_done && <Check className="w-4 h-4" />}
      </button>

      <div className="flex-1 min-w-0 flex items-center gap-2">
        {hasTime && (
          <span className="text-xs font-medium tabular-nums text-white/45 shrink-0">
            {timeLabel}
          </span>
        )}
        {editing ? (
          <input
            ref={editInputRef}
            value={draft}
            onChange={e => setDraft(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                e.preventDefault()
                commitEdit()
              } else if (e.key === 'Escape') {
                e.preventDefault()
                cancelEdit()
              }
            }}
            disabled={isBusy}
            className="flex-1 min-w-0 bg-white/10 border border-white/25 rounded-md px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500/50"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className={`flex-1 min-w-0 text-left text-sm leading-snug rounded-md px-1 py-0.5 -mx-1 hover:bg-white/5 transition ${
              task.is_done ? 'line-through text-white/40' : 'text-white'
            }`}
          >
            {task.title}
          </button>
        )}
      </div>

      {showAssignee && task.assignee_name && (
        <span className="text-xs text-white/35 truncate max-w-[7rem] shrink-0">
          {task.assignee_name}
        </span>
      )}

      <button
        type="button"
        onClick={onDelete}
        className="flex-shrink-0 p-1.5 rounded-lg text-white/20 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  )
}
