import { useState, useRef, useEffect, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Check, Trash2, ChevronLeft, ChevronRight, Users, User as UserIcon, Loader2, Send } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { dailyTasksApi, type DailyTask, type DailyTaskCreate } from '../services/dailyTasks'
import { usersApi } from '../services/users'
import { UserRole } from '../types/user'
import { format, addDays, subDays, isToday } from 'date-fns'
import { ru } from 'date-fns/locale'

export default function DailyPlanner() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()

  const [selectedDate, setSelectedDate] = useState(new Date())
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [showAllUsers, setShowAllUsers] = useState(false)
  const [assigneeId, setAssigneeId] = useState<string | undefined>(undefined)
  const [showAssigneeDropdown, setShowAssigneeDropdown] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const dateStr = format(selectedDate, 'yyyy-MM-dd')
  const isVP4PR = user?.role === UserRole.VP4PR || user?.role === ('vp4pr' as UserRole)
  const isCoordinator = user && (String(user.role).includes('coordinator') || isVP4PR)

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

  const createMutation = useMutation({
    mutationFn: (data: DailyTaskCreate) => dailyTasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['daily-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['daily-tasks-stats'] })
      setNewTaskTitle('')
      setAssigneeId(undefined)
    },
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_done }: { id: string; is_done: boolean }) =>
      dailyTasksApi.update(id, { is_done }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['daily-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['daily-tasks-stats'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => dailyTasksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['daily-tasks'] })
      queryClient.invalidateQueries({ queryKey: ['daily-tasks-stats'] })
    },
  })

  const handleCreate = () => {
    const title = newTaskTitle.trim()
    if (!title) return
    createMutation.mutate({
      title,
      date: dateStr,
      assignee_id: assigneeId || undefined,
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleCreate()
    }
  }

  const pendingTasks = tasks.filter(t => !t.is_done)
  const doneTasks = tasks.filter(t => t.is_done)

  const selectedAssignee = activeUsers.find(u => u.id === assigneeId)
  const progressPct = stats ? (stats.total > 0 ? Math.round((stats.done / stats.total) * 100) : 0) : 0

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-5">
      {/* Заголовок + навигация по датам */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Планёрка</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSelectedDate(d => subDays(d, 1))}
            className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
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
            onClick={() => setSelectedDate(d => addDays(d, 1))}
            className="p-2 rounded-lg hover:bg-white/10 text-white/70 hover:text-white transition"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Дата */}
      <p className="text-white/50 text-sm -mt-2">
        {format(selectedDate, 'EEEE, d MMMM yyyy', { locale: ru })}
      </p>

      {/* Прогресс */}
      {stats && stats.total > 0 && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-sm text-white/60">
            <span>Выполнено {stats.done} из {stats.total}</span>
            <span>{progressPct}%</span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{
                width: `${progressPct}%`,
                background: progressPct === 100
                  ? 'linear-gradient(90deg, #22c55e, #16a34a)'
                  : 'linear-gradient(90deg, #3b82f6, #6366f1)',
              }}
            />
          </div>
        </div>
      )}

      {/* Переключатель мои / все */}
      {isCoordinator && (
        <div className="flex gap-2">
          <button
            onClick={() => setShowAllUsers(false)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${
              !showAllUsers ? 'bg-blue-500/30 text-blue-300 border border-blue-500/40' : 'bg-white/10 text-white/60 hover:text-white'
            }`}
          >
            <UserIcon className="w-4 h-4" /> Мои
          </button>
          <button
            onClick={() => setShowAllUsers(true)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition ${
              showAllUsers ? 'bg-blue-500/30 text-blue-300 border border-blue-500/40' : 'bg-white/10 text-white/60 hover:text-white'
            }`}
          >
            <Users className="w-4 h-4" /> Все
          </button>
        </div>
      )}

      {/* Ввод новой задачи */}
      <div className="flex gap-2 items-start">
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            value={newTaskTitle}
            onChange={e => setNewTaskTitle(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Новая задача..."
            className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder-white/40 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/30 transition text-sm"
          />
          {/* Выбор назначаемого */}
          {isCoordinator && (
            <div className="relative mt-2" ref={dropdownRef}>
              <button
                onClick={() => setShowAssigneeDropdown(!showAssigneeDropdown)}
                className="flex items-center gap-1.5 text-xs text-white/50 hover:text-white/80 transition"
              >
                <UserIcon className="w-3.5 h-3.5" />
                {selectedAssignee ? selectedAssignee.full_name : 'Назначить себе'}
              </button>
              {showAssigneeDropdown && (
                <div className="absolute bottom-full mb-1 left-0 z-50 w-56 max-h-48 overflow-y-auto bg-gray-800/95 backdrop-blur border border-white/20 rounded-lg shadow-xl">
                  <button
                    onClick={() => { setAssigneeId(undefined); setShowAssigneeDropdown(false) }}
                    className="w-full text-left px-3 py-2 text-sm text-white/80 hover:bg-white/10 transition"
                  >
                    Себе
                  </button>
                  {activeUsers.map(u => (
                    <button
                      key={u.id}
                      onClick={() => { setAssigneeId(u.id); setShowAssigneeDropdown(false) }}
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
        </div>
        <button
          onClick={handleCreate}
          disabled={!newTaskTitle.trim() || createMutation.isPending}
          className="flex-shrink-0 p-3 rounded-xl bg-blue-500/30 text-blue-300 hover:bg-blue-500/40 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {createMutation.isPending ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Список задач */}
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
          {/* Невыполненные */}
          {pendingTasks.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              showAssignee={showAllUsers}
              onToggle={() => toggleMutation.mutate({ id: task.id, is_done: true })}
              onDelete={() => deleteMutation.mutate(task.id)}
            />
          ))}

          {/* Разделитель */}
          {doneTasks.length > 0 && pendingTasks.length > 0 && (
            <div className="flex items-center gap-3 py-2">
              <div className="flex-1 h-px bg-white/10" />
              <span className="text-xs text-white/30">Выполнено ({doneTasks.length})</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
          )}

          {/* Выполненные */}
          {doneTasks.map(task => (
            <TaskItem
              key={task.id}
              task={task}
              showAssignee={showAllUsers}
              onToggle={() => toggleMutation.mutate({ id: task.id, is_done: false })}
              onDelete={() => deleteMutation.mutate(task.id)}
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
}: {
  task: DailyTask
  showAssignee: boolean
  onToggle: () => void
  onDelete: () => void
}) {
  return (
    <div
      className={`group flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
        task.is_done
          ? 'bg-white/5 opacity-60'
          : 'bg-white/10 hover:bg-white/15'
      }`}
    >
      {/* Чекбокс */}
      <button
        onClick={onToggle}
        className={`flex-shrink-0 w-6 h-6 rounded-lg border-2 flex items-center justify-center transition-all ${
          task.is_done
            ? 'bg-green-500/30 border-green-500/60 text-green-400'
            : 'border-white/30 hover:border-blue-400 hover:bg-blue-500/10'
        }`}
      >
        {task.is_done && <Check className="w-4 h-4" />}
      </button>

      {/* Текст */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm leading-snug ${
          task.is_done ? 'line-through text-white/40' : 'text-white'
        }`}>
          {task.title}
        </p>
        {showAssignee && task.assignee_name && (
          <p className="text-xs text-white/40 mt-0.5">{task.assignee_name}</p>
        )}
      </div>

      {/* Удалить */}
      <button
        onClick={onDelete}
        className="flex-shrink-0 p-1.5 rounded-lg text-white/20 hover:text-red-400 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
      >
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  )
}
