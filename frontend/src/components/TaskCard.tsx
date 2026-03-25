import { useState, useEffect } from 'react'
import { Clock, AlertCircle, MessageSquare, ChevronDown, ChevronUp, Image as ImageIcon, Camera, UserPlus, UserMinus, RefreshCw, CheckCircle, Pencil, Trash2, X, Save, Plus } from 'lucide-react'
import { useParallaxHover } from '../hooks/useParallaxHover'
import { Task, TaskUpdate, TaskStageCreate, TaskStageUpdate } from '../types/task'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { telegramChatsApi, TaskChatResponse } from '../services/telegramChats'
import { galleryApi } from '../services/gallery'
import { tasksApi } from '../services/tasks'
import { usersApi, UserProfile } from '../services/users'
import TaskQuestions from './TaskQuestions'
import TaskFiles from './TaskFiles'
import StageFileUpload from './StageFileUpload'
import { isPrivileged, isCoordinatorOrAbove } from '../types/user'

const typeLabels: Record<string, string> = {
  smm: 'SMM',
  design: 'Дизайн',
  channel: 'Channel',
  prfr: 'PR-FR',
  multitask: 'Многозадачная',
}

const statusLabels: Record<string, string> = {
  draft: 'Черновик',
  open: 'Открыта',
  assigned: 'Назначена',
  in_progress: 'В работе',
  review: 'На проверке',
  completed: 'Завершена',
  cancelled: 'Отменена',
}

const priorityColors: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  medium: 'bg-status-yellow/20 text-status-yellow',
  high: 'bg-status-red/20 text-status-red',
  critical: 'bg-status-red text-white',
}

interface TaskCardProps {
  task: Task
}

export default function TaskCard({ task }: TaskCardProps) {
  const parallax = useParallaxHover(8)
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [expanded, setExpanded] = useState(false)
  const [selectedRole, setSelectedRole] = useState<string | null>(null)
  const [showReassign, setShowReassign] = useState(false)
  const [reassignUserId, setReassignUserId] = useState('')
  const [isEditing, setIsEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [editData, setEditData] = useState<TaskUpdate>({})

  const { data: taskChat } = useQuery<TaskChatResponse>({
    queryKey: ['task-chat', task.id],
    queryFn: () => telegramChatsApi.getTaskChat(task.id),
    enabled: !!user?.is_active,
  })

  const { data: exampleProjects } = useQuery({
    queryKey: ['gallery', 'examples', task.example_project_ids],
    queryFn: async () => {
      if (!task.example_project_ids || task.example_project_ids.length === 0) return []
      const results = await Promise.all(
        task.example_project_ids.map(() => galleryApi.getGallery({ limit: 1 }))
      )
      return results.flatMap((r) => r.items)
    },
    enabled: !!task.example_project_ids && task.example_project_ids.length > 0,
  })

  const { data: activeUsers } = useQuery({
    queryKey: ['users-active'],
    queryFn: () => usersApi.getUsers({ is_active: true, limit: 100 }),
    enabled: showReassign || isEditing,
  })

  const isRegistered = !!user?.is_active
  const isCoordinator = user ? isCoordinatorOrAbove(user.role) : false
  const isVP4PR = user ? isPrivileged(user.role) : false
  const isAssignedToMe = task.assignments?.some(a => a.user_id === user?.id && a.status !== 'cancelled')
  const canTakeTask = isRegistered && !isAssignedToMe && ['open', 'draft'].includes(task.status)

  const invalidateTaskQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['tasks'] })
    queryClient.invalidateQueries({ queryKey: ['task', task.id] })
  }

  const assignMutation = useMutation({
    mutationFn: () => tasksApi.assignTask(task.id),
    onSuccess: invalidateTaskQueries,
  })

  const cancelAssignmentMutation = useMutation({
    mutationFn: (assignmentId: string) => tasksApi.cancelAssignment(task.id, assignmentId),
    onSuccess: invalidateTaskQueries,
  })

  const reassignMutation = useMutation({
    mutationFn: (newUserId: string) => tasksApi.reassignTask(task.id, newUserId),
    onSuccess: () => {
      invalidateTaskQueries()
      setShowReassign(false)
      setReassignUserId('')
    },
  })

  const completeMutation = useMutation({
    mutationFn: () => tasksApi.completeTask(task.id),
    onSuccess: invalidateTaskQueries,
  })

  const updateMutation = useMutation({
    mutationFn: (data: TaskUpdate) => tasksApi.updateTask(task.id, data),
    onSuccess: () => {
      invalidateTaskQueries()
      setIsEditing(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => tasksApi.deleteTask(task.id),
    onSuccess: () => {
      invalidateTaskQueries()
      setConfirmDelete(false)
    },
  })

  const startEditing = () => {
    setEditData({
      title: task.title,
      description: task.description || '',
      priority: task.priority as TaskUpdate['priority'],
      status: task.status as TaskUpdate['status'],
      due_date: task.due_date || undefined,
    })
    setIsEditing(true)
  }

  const saveEdit = () => {
    const changes: TaskUpdate = {}
    if (editData.title !== task.title) changes.title = editData.title
    if (editData.description !== (task.description || '')) changes.description = editData.description
    if (editData.priority !== task.priority) changes.priority = editData.priority
    if (editData.status !== task.status) changes.status = editData.status
    if (editData.due_date !== task.due_date) changes.due_date = editData.due_date
    if (Object.keys(changes).length > 0) {
      updateMutation.mutate(changes)
    } else {
      setIsEditing(false)
    }
  }

  const formatDateForInput = (dateStr?: string) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const pad = (n: number) => n.toString().padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  // Deadline countdown
  const [countdown, setCountdown] = useState('')
  const [countdownColor, setCountdownColor] = useState('text-white/60')
  useEffect(() => {
    if (!task.due_date) return
    const update = () => {
      const now = new Date().getTime()
      const deadline = new Date(task.due_date!).getTime()
      const diff = deadline - now
      if (diff <= 0) {
        const overdue = Math.abs(diff)
        const hours = Math.floor(overdue / 3600000)
        const mins = Math.floor((overdue % 3600000) / 60000)
        setCountdown(`Просрочено на ${hours}ч ${mins}мин`)
        setCountdownColor('text-red-400 animate-pulse')
        return
      }
      const days = Math.floor(diff / 86400000)
      const hours = Math.floor((diff % 86400000) / 3600000)
      const mins = Math.floor((diff % 3600000) / 60000)
      if (days > 0) setCountdown(`${days}д ${hours}ч`)
      else if (hours > 0) setCountdown(`${hours}ч ${mins}мин`)
      else setCountdown(`${mins}мин`)
      if (days >= 3) setCountdownColor('text-green-400')
      else if (days >= 1) setCountdownColor('text-yellow-400')
      else setCountdownColor('text-red-400')
    }
    update()
    const interval = setInterval(update, 60000)
    return () => clearInterval(interval)
  }, [task.due_date])

  const getRoleName = (role: string) => {
    const names: Record<string, string> = { smm: 'SMM', design: 'Design', channel: 'Channel', prfr: 'PR-FR' }
    return names[role] || role
  }

  const getUserDisplayName = (assignment: { user_id: string; user_name?: string }) => {
    return assignment.user_name || assignment.user_id.slice(0, 8) + '...'
  }

  return (
    <div
      ref={parallax.ref}
      style={{ transform: parallax.transform }}
      className={`glass-enhanced ${theme} rounded-xl p-6 card-3d text-white parallax-hover touch-manipulation`}
    >
      {/* Toolbar VP4PR: Edit / Delete */}
      {isCoordinator && !isEditing && (
        <div className="flex items-center justify-end gap-2 mb-3">
          <button
            onClick={startEditing}
            className="text-white/60 hover:text-white text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-white/10 transition-all"
            title="Редактировать задачу"
          >
            <Pencil className="h-3.5 w-3.5" />
            <span>Редактировать</span>
          </button>
          {isVP4PR && (
            <button
              onClick={() => setConfirmDelete(true)}
              className="text-red-400/70 hover:text-red-400 text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-red-500/10 transition-all"
              title="Удалить задачу"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Удалить</span>
            </button>
          )}
        </div>
      )}

      {/* Confirmation dialog for delete */}
      {confirmDelete && (
        <div className="mb-4 p-4 bg-red-500/20 border border-red-500/50 rounded-lg">
          <p className="text-white text-sm mb-3">Удалить задачу «{task.title}»? Это действие нельзя отменить.</p>
          <div className="flex gap-2">
            <button
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="bg-red-600 text-white text-sm px-4 py-1.5 rounded hover:bg-red-500 disabled:opacity-50"
            >
              {deleteMutation.isPending ? 'Удаляю...' : 'Да, удалить'}
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="bg-white/10 text-white text-sm px-4 py-1.5 rounded hover:bg-white/20"
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* Edit mode */}
      {isEditing ? (
        <div className="space-y-4 mb-4">
          <div>
            <label className="text-white/60 text-xs mb-1 block">Название</label>
            <input
              type="text"
              value={editData.title || ''}
              onChange={e => setEditData({ ...editData, title: e.target.value })}
              className="w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary"
            />
          </div>
          <div>
            <label className="text-white/60 text-xs mb-1 block">Описание</label>
            <textarea
              value={editData.description || ''}
              onChange={e => setEditData({ ...editData, description: e.target.value })}
              rows={3}
              className="w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary resize-y"
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="text-white/60 text-xs mb-1 block">Дедлайн</label>
              <input
                type="datetime-local"
                value={formatDateForInput(editData.due_date)}
                onChange={e => setEditData({ ...editData, due_date: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
                className="w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary [color-scheme:dark]"
              />
            </div>
            <div>
              <label className="text-white/60 text-xs mb-1 block">Приоритет</label>
              <select
                value={editData.priority || ''}
                onChange={e => setEditData({ ...editData, priority: e.target.value as TaskUpdate['priority'] })}
                className="w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary [&>option]:bg-gray-800"
              >
                <option value="low">Низкий</option>
                <option value="medium">Средний</option>
                <option value="high">Высокий</option>
                <option value="critical">Критичный</option>
              </select>
            </div>
            <div>
              <label className="text-white/60 text-xs mb-1 block">Статус</label>
              <select
                value={editData.status || ''}
                onChange={e => setEditData({ ...editData, status: e.target.value as TaskUpdate['status'] })}
                className="w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary [&>option]:bg-gray-800"
              >
                <option value="draft">Черновик</option>
                <option value="open">Открыта</option>
                <option value="assigned">Назначена</option>
                <option value="in_progress">В работе</option>
                <option value="review">На проверке</option>
                <option value="completed">Завершена</option>
                <option value="cancelled">Отменена</option>
              </select>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={saveEdit}
              disabled={updateMutation.isPending}
              className="bg-best-primary text-white px-4 py-2 rounded-lg hover:bg-best-primary/80 flex items-center gap-2 disabled:opacity-50 text-sm"
            >
              <Save className="h-4 w-4" />
              {updateMutation.isPending ? 'Сохраняю...' : 'Сохранить'}
            </button>
            <button
              onClick={() => setIsEditing(false)}
              className="bg-white/10 text-white px-4 py-2 rounded-lg hover:bg-white/20 flex items-center gap-2 text-sm"
            >
              <X className="h-4 w-4" />
              Отмена
            </button>
          </div>
          {updateMutation.isError && (
            <p className="text-red-400 text-xs">{(updateMutation.error as Error)?.message || 'Ошибка сохранения'}</p>
          )}
        </div>
      ) : (
        <>
          {task.thumbnail_image_url && (
            <img
              src={task.thumbnail_image_url}
              alt={task.title}
              className="w-full h-48 object-cover rounded-lg mb-4"
            />
          )}

          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center space-x-3 mb-2 flex-wrap gap-y-2">
                <span className="px-3 py-1 bg-best-primary/10 text-best-primary rounded-full text-sm font-medium">
                  {typeLabels[task.type] || task.type}
                </span>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${priorityColors[task.priority] || ''}`}>
                  {task.priority === 'critical' ? 'Критично' :
                   task.priority === 'high' ? 'Высокий' :
                   task.priority === 'medium' ? 'Средний' : 'Низкий'}
                </span>
                {task.equipment_available && (
                  <span className="px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-sm font-medium flex items-center space-x-1">
                    <Camera className="h-3 w-3" />
                    <span>Оборудование</span>
                  </span>
                )}
              </div>
              <h3 className={`text-xl font-semibold text-white mb-2 text-readable ${theme}`}>
                {task.title}
              </h3>
              {task.description && (
                <p className={`text-white mb-4 text-readable ${theme}`}>{task.description}</p>
              )}
            </div>
          </div>
        </>
      )}

      {/* ТЗ по ролям */}
      {!isEditing && task.role_specific_requirements && Object.keys(task.role_specific_requirements).length > 0 && (
        <div className="mb-4">
          <div className="flex items-center space-x-2 mb-2">
            <span className={`text-white font-semibold text-readable ${theme}`}>ТЗ по ролям:</span>
            <div className="flex flex-wrap gap-2">
              {Object.keys(task.role_specific_requirements).map((role) => (
                <button
                  key={role}
                  onClick={() => setSelectedRole(selectedRole === role ? null : role)}
                  className={`px-3 py-1 rounded-lg text-sm transition-all ${
                    selectedRole === role
                      ? 'bg-best-primary text-white'
                      : 'bg-white/10 text-white/70 hover:bg-white/20'
                  }`}
                >
                  {getRoleName(role)}
                </button>
              ))}
            </div>
          </div>
          {selectedRole && task.role_specific_requirements[selectedRole as keyof typeof task.role_specific_requirements] && (
            <div className="p-3 bg-white/10 rounded-lg border border-white/20 mb-2">
              <p className={`text-white text-readable ${theme}`}>
                {task.role_specific_requirements[selectedRole as keyof typeof task.role_specific_requirements]}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Контрольные точки (этапы) */}
      {!isEditing && (task.stages?.length || isCoordinator) ? (
        <StagesSection
          task={task}
          isCoordinator={!!isCoordinator}
          isRegistered={isRegistered}
          theme={theme}
          onInvalidate={invalidateTaskQueries}
        />
      ) : null}

      {!isEditing && <TaskQuestions taskId={task.id} />}
      {!isEditing && <TaskFiles taskId={task.id} />}

      {/* Примеры прошлых работ */}
      {!isEditing && exampleProjects && exampleProjects.length > 0 && (
        <div className="mb-4">
          <h4 className={`text-white font-semibold mb-2 flex items-center space-x-2 text-readable ${theme}`}>
            <ImageIcon className="h-4 w-4" />
            <span>Примеры прошлых работ:</span>
          </h4>
          <div className="grid grid-cols-2 gap-2">
            {exampleProjects.map((project) => (
              <div key={project.id} className="p-2 bg-white/10 rounded-lg cursor-pointer hover:bg-white/20 transition-all">
                {project.thumbnail_url && (
                  <img src={project.thumbnail_url} alt={project.title} className="w-full h-20 object-cover rounded mb-1" />
                )}
                <p className={`text-white text-xs text-readable ${theme}`}>{project.title}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Назначения (для координаторов) */}
      {isCoordinator && task.assignments && task.assignments.length > 0 && (
        <div className="mb-4 p-3 bg-white/5 rounded-lg">
          <h4 className={`text-white/80 font-semibold mb-2 text-sm text-readable ${theme}`}>Назначенные:</h4>
          <div className="space-y-2">
            {task.assignments.filter(a => a.status !== 'cancelled').map(a => (
              <div key={a.id} className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="text-white text-sm">{getUserDisplayName(a)}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    a.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                    a.status === 'in_progress' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-blue-500/20 text-blue-400'
                  }`}>
                    {a.status === 'assigned' ? 'Назначен' : a.status === 'in_progress' ? 'В работе' : a.status === 'completed' ? 'Завершил' : a.status}
                  </span>
                </div>
                {isVP4PR && (
                  <button
                    onClick={() => cancelAssignmentMutation.mutate(a.id)}
                    disabled={cancelAssignmentMutation.isPending}
                    className="text-red-400 hover:text-red-300 text-xs flex items-center space-x-1"
                    title="Отменить назначение"
                  >
                    <UserMinus className="h-3 w-3" />
                    <span>Снять</span>
                  </button>
                )}
              </div>
            ))}
          </div>
          {isVP4PR && (
            <button
              onClick={() => setShowReassign(!showReassign)}
              className="mt-2 text-best-primary hover:text-best-primary/80 text-xs flex items-center space-x-1"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Переназначить</span>
            </button>
          )}
          {showReassign && (
            <div className="mt-2 flex items-center space-x-2">
              <select
                value={reassignUserId}
                onChange={(e) => setReassignUserId(e.target.value)}
                className="flex-1 bg-white/10 text-white text-xs rounded px-2 py-1 border border-white/20 [&>option]:bg-gray-800"
              >
                <option value="">Выберите человека</option>
                {activeUsers?.items?.map((u: UserProfile) => (
                  <option key={u.id} value={u.id}>{u.full_name}</option>
                ))}
              </select>
              <button
                onClick={() => reassignUserId && reassignMutation.mutate(reassignUserId)}
                disabled={!reassignUserId || reassignMutation.isPending}
                className="bg-best-primary text-white text-xs px-3 py-1 rounded hover:bg-best-primary/80 disabled:opacity-50"
              >
                OK
              </button>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      {!isEditing && (
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className={`flex items-center space-x-4 text-sm text-white text-readable ${theme}`}>
            {task.due_date && (
              <div className="flex items-center space-x-1">
                <Clock className="h-4 w-4" />
                <span>
                  {new Date(task.due_date).toLocaleDateString('ru-RU')}{' '}
                  {new Date(task.due_date).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            )}
            {countdown && (
              <span className={`text-xs font-medium ${countdownColor}`}>{countdown}</span>
            )}
            <div className="flex items-center space-x-1">
              <AlertCircle className="h-4 w-4" />
              <span>{statusLabels[task.status] || task.status}</span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {isCoordinator && task.drive_folder_id && (
              <a
                href={`https://drive.google.com/drive/folders/${task.drive_folder_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 bg-white/10 rounded-lg hover:bg-white/20 transition-all text-white/70 hover:text-white"
                title="Открыть папку в Google Drive"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12.01 1.485c-2.082 0-3.754.02-5.143.123-1.404.104-2.536.37-3.46 1.293-.924.923-1.19 2.055-1.293 3.459-.104 1.39-.124 3.062-.124 5.144 0 2.082.02 3.754.123 5.143.104 1.404.37 2.536 1.293 3.46.923.924 2.055 1.19 3.459 1.293 1.39.104 3.062.124 5.144.124 2.082 0 3.754-.02 5.143-.123 1.404-.104 2.536-.37 3.46-1.293.924-.923 1.19-2.055 1.293-3.459.104-1.39.124-3.062.124-5.144 0-2.082-.02-3.754-.123-5.143-.104-1.404-.37-2.536-1.293-3.46-.923-.924-2.055-1.19-3.459-1.293-1.39-.104-3.062-.124-5.144-.124zm-1.14 5.162h5.535c.87 0 1.58.71 1.58 1.58v1.58h-7.115v-3.16zm-1.58 0v3.16h-3.16v-1.58c0-.87.71-1.58 1.58-1.58h1.58zm-3.16 4.74h11.855v6.32c0 .87-.71 1.58-1.58 1.58h-8.695c-.87 0-1.58-.71-1.58-1.58v-6.32z"/>
                </svg>
              </a>
            )}

            <button
              onClick={() => setExpanded(!expanded)}
              className="p-2 rounded-lg hover:bg-white/10 transition-all"
            >
              {expanded ? <ChevronUp className="h-4 w-4 text-white" /> : <ChevronDown className="h-4 w-4 text-white" />}
            </button>
            {isRegistered && taskChat?.exists && taskChat.invite_link && (
              <a
                href={taskChat.invite_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center space-x-2 bg-best-primary/20 text-white px-3 py-2 rounded-lg hover:bg-best-primary/30 transition-all card-3d border border-best-primary/50"
                title="Чат задачи"
              >
                <MessageSquare className="h-4 w-4" />
                <span className="text-sm">Чат</span>
              </a>
            )}
            {canTakeTask && (
              <button
                onClick={() => assignMutation.mutate()}
                disabled={assignMutation.isPending}
                className="bg-best-primary text-white px-4 py-2 rounded-lg hover:bg-best-primary/80 transition-all card-3d border border-best-primary/50 flex items-center space-x-2 disabled:opacity-50"
              >
                <UserPlus className="h-4 w-4" />
                <span>{assignMutation.isPending ? 'Назначаю...' : 'Взять задачу'}</span>
              </button>
            )}
            {isAssignedToMe && task.status !== 'completed' && task.status !== 'cancelled' && (
              <button
                onClick={() => completeMutation.mutate()}
                disabled={completeMutation.isPending}
                className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-500 transition-all card-3d border border-green-500/50 flex items-center space-x-2 disabled:opacity-50"
              >
                <CheckCircle className="h-4 w-4" />
                <span>{completeMutation.isPending ? 'Завершаю...' : 'Завершить'}</span>
              </button>
            )}
            {isVP4PR && !showReassign && (
              <button
                onClick={() => setShowReassign(true)}
                className="bg-white/10 text-white px-3 py-2 rounded-lg hover:bg-white/20 transition-all flex items-center space-x-1"
                title="Назначить человека"
              >
                <UserPlus className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}
      {assignMutation.isError && (
        <p className="text-red-400 text-xs mt-2">{(assignMutation.error as Error)?.message || 'Ошибка при назначении'}</p>
      )}
    </div>
  )
}

const stageColorOptions = ['green', 'yellow', 'red', 'purple', 'blue'] as const
const stageColorNames: Record<string, string> = {
  green: 'Процесс',
  yellow: 'Согласование',
  red: 'Дедлайн',
  purple: 'Ревью',
  blue: 'Буфер',
}

function StagesSection({ task, isCoordinator, isRegistered, theme, onInvalidate }: {
  task: Task
  isCoordinator: boolean
  isRegistered: boolean
  theme: string
  onInvalidate: () => void
}) {
  const queryClient = useQueryClient()
  const [editingStageId, setEditingStageId] = useState<string | null>(null)
  const [editStage, setEditStage] = useState<TaskStageUpdate>({})
  const [showAddStage, setShowAddStage] = useState(false)
  const [newStage, setNewStage] = useState<TaskStageCreate>({ stage_name: '', stage_order: (task.stages?.length || 0) + 1, status_color: 'green' })

  const createStageMutation = useMutation({
    mutationFn: (data: TaskStageCreate) => tasksApi.createStage(task.id, data),
    onSuccess: () => {
      onInvalidate()
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setShowAddStage(false)
      setNewStage({ stage_name: '', stage_order: (task.stages?.length || 0) + 2, status_color: 'green' })
    },
  })

  const updateStageMutation = useMutation({
    mutationFn: ({ stageId, data }: { stageId: string; data: TaskStageUpdate }) => tasksApi.updateStage(task.id, stageId, data),
    onSuccess: () => {
      onInvalidate()
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setEditingStageId(null)
    },
  })

  const deleteStageMutation = useMutation({
    mutationFn: (stageId: string) => tasksApi.deleteStage(task.id, stageId),
    onSuccess: () => {
      onInvalidate()
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const startEdit = (stage: Task['stages'] extends (infer S)[] | undefined ? NonNullable<S> : never) => {
    setEditingStageId(stage.id)
    setEditStage({
      stage_name: stage.stage_name,
      stage_order: stage.stage_order,
      due_date: stage.due_date || undefined,
      status: stage.status as TaskStageUpdate['status'],
      status_color: stage.status_color as TaskStageUpdate['status_color'],
    })
  }

  const saveEdit = () => {
    if (!editingStageId) return
    updateStageMutation.mutate({ stageId: editingStageId, data: editStage })
  }

  const formatDateForInput = (dateStr?: string | null) => {
    if (!dateStr) return ''
    const d = new Date(dateStr)
    const pad = (n: number) => n.toString().padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  const getStageStatusColor = (status: string, color?: string) => {
    if (color) {
      const colorMap: Record<string, string> = {
        green: 'bg-green-500/20 text-green-400 border-green-500/50',
        yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
        red: 'bg-red-500/20 text-red-400 border-red-500/50',
        purple: 'bg-purple-500/20 text-purple-400 border-purple-500/50',
        blue: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
      }
      return colorMap[color] || 'bg-white/10 text-white border-white/20'
    }
    const statusMap: Record<string, string> = {
      completed: 'bg-green-500/20 text-green-400 border-green-500/50',
      in_progress: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
      pending: 'bg-gray-500/20 text-gray-400 border-gray-500/50',
    }
    return statusMap[status] || 'bg-white/10 text-white border-white/20'
  }

  const sortedStages = [...(task.stages || [])].sort((a, b) => a.stage_order - b.stage_order)

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className={`text-white font-semibold text-readable ${theme}`}>
          Этапы ({sortedStages.length})
        </h4>
        {isCoordinator && (
          <button
            onClick={() => setShowAddStage(!showAddStage)}
            className="text-best-primary hover:text-best-primary/80 text-xs flex items-center gap-1"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Добавить</span>
          </button>
        )}
      </div>

      {showAddStage && (
        <div className="mb-3 p-3 bg-white/5 rounded-lg border border-white/10 space-y-2">
          <input
            type="text"
            value={newStage.stage_name}
            onChange={e => setNewStage({ ...newStage, stage_name: e.target.value })}
            placeholder="Название этапа"
            className="w-full bg-white/10 text-white rounded px-3 py-1.5 border border-white/20 focus:outline-none focus:ring-1 focus:ring-best-primary text-sm"
            autoFocus
            onKeyDown={e => { if (e.key === 'Enter' && newStage.stage_name.trim()) createStageMutation.mutate(newStage) }}
          />
          <div className="flex items-center gap-2">
            <input
              type="datetime-local"
              value={newStage.due_date || ''}
              onChange={e => setNewStage({ ...newStage, due_date: e.target.value || undefined })}
              className="flex-1 bg-white/10 text-white rounded px-2 py-1 border border-white/20 focus:outline-none text-xs [color-scheme:dark]"
            />
            <div className="flex gap-1">
              {stageColorOptions.map(c => (
                <button
                  key={c}
                  onClick={() => setNewStage({ ...newStage, status_color: c })}
                  className={`w-5 h-5 rounded-full border-2 transition-all ${
                    newStage.status_color === c ? 'scale-125 border-white' : 'border-transparent opacity-60 hover:opacity-100'
                  }`}
                  style={{ backgroundColor: c === 'green' ? '#22c55e' : c === 'yellow' ? '#eab308' : c === 'red' ? '#ef4444' : c === 'purple' ? '#a855f7' : '#3b82f6' }}
                  title={stageColorNames[c]}
                />
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => newStage.stage_name.trim() && createStageMutation.mutate(newStage)}
              disabled={!newStage.stage_name.trim() || createStageMutation.isPending}
              className="bg-best-primary text-white px-3 py-1 rounded text-xs hover:bg-best-primary/80 disabled:opacity-50"
            >
              {createStageMutation.isPending ? 'Создаю...' : 'Создать'}
            </button>
            <button onClick={() => setShowAddStage(false)} className="bg-white/10 text-white px-3 py-1 rounded text-xs hover:bg-white/20">
              Отмена
            </button>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        {sortedStages.map(stage => (
          <div key={stage.id}>
            {editingStageId === stage.id ? (
              <div className="p-2.5 bg-white/5 rounded-lg border border-best-primary/30 space-y-2">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={editStage.stage_name || ''}
                    onChange={e => setEditStage({ ...editStage, stage_name: e.target.value })}
                    className="flex-1 bg-white/10 text-white rounded px-2 py-1 border border-white/20 focus:outline-none focus:ring-1 focus:ring-best-primary text-sm"
                    autoFocus
                  />
                  <select
                    value={editStage.status || stage.status}
                    onChange={e => setEditStage({ ...editStage, status: e.target.value as TaskStageUpdate['status'] })}
                    className="bg-white/10 text-white rounded px-2 py-1 border border-white/20 text-xs [&>option]:bg-gray-800"
                  >
                    <option value="pending">Не начато</option>
                    <option value="in_progress">В работе</option>
                    <option value="completed">Выполнено</option>
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="datetime-local"
                    value={formatDateForInput(editStage.due_date)}
                    onChange={e => setEditStage({ ...editStage, due_date: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
                    className="flex-1 bg-white/10 text-white rounded px-2 py-1 border border-white/20 focus:outline-none text-xs [color-scheme:dark]"
                  />
                  <div className="flex gap-1">
                    {stageColorOptions.map(c => (
                      <button
                        key={c}
                        onClick={() => setEditStage({ ...editStage, status_color: c as TaskStageUpdate['status_color'] })}
                        className={`w-4 h-4 rounded-full border-2 transition-all ${
                          (editStage.status_color || stage.status_color) === c ? 'scale-125 border-white' : 'border-transparent opacity-60 hover:opacity-100'
                        }`}
                        style={{ backgroundColor: c === 'green' ? '#22c55e' : c === 'yellow' ? '#eab308' : c === 'red' ? '#ef4444' : c === 'purple' ? '#a855f7' : '#3b82f6' }}
                      />
                    ))}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={saveEdit} disabled={updateStageMutation.isPending}
                    className="bg-best-primary text-white px-3 py-1 rounded text-xs hover:bg-best-primary/80 disabled:opacity-50 flex items-center gap-1">
                    <Save className="h-3 w-3" />{updateStageMutation.isPending ? '...' : 'OK'}
                  </button>
                  <button onClick={() => setEditingStageId(null)} className="bg-white/10 text-white px-3 py-1 rounded text-xs hover:bg-white/20">
                    Отмена
                  </button>
                  {isCoordinator && (
                    <button onClick={() => { if (confirm('Удалить этап?')) deleteStageMutation.mutate(stage.id) }}
                      className="ml-auto text-red-400/70 hover:text-red-400 text-xs flex items-center gap-1 px-2 py-1 rounded hover:bg-red-500/10">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div
                className={`flex items-center gap-2 p-2 bg-white/5 rounded-lg group transition-all ${isCoordinator ? 'cursor-pointer hover:bg-white/10' : ''}`}
                onClick={() => isCoordinator && startEdit(stage)}
              >
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0`}
                  style={{ backgroundColor: stage.status_color === 'green' ? '#22c55e' : stage.status_color === 'yellow' ? '#eab308' : stage.status_color === 'red' ? '#ef4444' : stage.status_color === 'purple' ? '#a855f7' : '#3b82f6' }}
                />
                <span className="text-white text-sm flex-1 truncate">{stage.stage_name}</span>
                {stage.due_date && (
                  <span className="text-white/50 text-xs flex-shrink-0">
                    {new Date(stage.due_date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}
                    {' '}
                    {new Date(stage.due_date).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border flex-shrink-0 ${getStageStatusColor(stage.status, stage.status_color)}`}>
                  {stage.status === 'completed' ? 'Готово' : stage.status === 'in_progress' ? 'В работе' : 'Ожидание'}
                </span>
                {isRegistered && (
                  <div onClick={e => e.stopPropagation()}>
                    <StageFileUpload taskId={task.id} stageId={stage.id} stageName={stage.stage_name} />
                  </div>
                )}
                {isCoordinator && (
                  <Pencil className="h-3 w-3 text-white/20 group-hover:text-white/60 flex-shrink-0 transition-colors" />
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
