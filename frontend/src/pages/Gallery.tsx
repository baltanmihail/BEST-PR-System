import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Image, Loader2, Film, Filter, Eye, Heart, Tag, User, Calendar, RefreshCw, CheckSquare, Link as LinkIcon, Save, X } from 'lucide-react'
import { galleryApi, type GalleryItem } from '../services/gallery'
import { tasksApi } from '../services/tasks'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { UserRole } from '../types/user'

export default function Gallery() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedItem, setSelectedItem] = useState<GalleryItem | null>(null)
  const [isLinkingTask, setIsLinkingTask] = useState(false)
  const [selectedTaskId, setSelectedTaskId] = useState<string>('')

  const isCoordinator = user && (
    user.role === UserRole.COORDINATOR_SMM ||
    user.role === UserRole.COORDINATOR_DESIGN ||
    user.role === UserRole.COORDINATOR_CHANNEL ||
    user.role === UserRole.COORDINATOR_PRFR ||
    user.role === UserRole.VP4PR
  )

  const syncMutation = useMutation({
    mutationFn: () => galleryApi.syncFromDrive(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      alert(data.message || `Синхронизировано ${data.added} новых файлов`)
    },
    onError: (error: any) => {
      console.error(error)
      alert(error.response?.data?.detail || 'Ошибка синхронизации')
    }
  })

  const { data, isLoading } = useQuery({
    queryKey: ['gallery', selectedCategory],
    queryFn: () =>
      galleryApi.getGallery({
        limit: 50,
        category: selectedCategory !== 'all' ? (selectedCategory as 'photo' | 'video' | 'final' | 'wip') : undefined,
      }),
  })

  const { data: tasksData } = useQuery({
    queryKey: ['tasks', 'completed'],
    queryFn: () => tasksApi.getTasks({ status: 'completed', limit: 20 }),
    enabled: isLinkingTask
  })

  const linkTaskMutation = useMutation({
    mutationFn: ({ itemId, taskId }: { itemId: string, taskId: string }) => 
      galleryApi.updateGalleryItem(itemId, { task_id: taskId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      setSelectedItem(prev => prev ? { ...prev, task_id: selectedTaskId } : null) // Optimistic updateish
      setIsLinkingTask(false)
      // Закрываем и открываем заново, чтобы обновить данные (или можно сделать refetch)
      setSelectedItem(null) 
      alert('Задача успешно привязана!')
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка привязки задачи')
    }
  })

  const items = data?.items || []

  const getCategoryName = (category: string) => {
    const names: Record<string, string> = {
      photo: 'Фото',
      video: 'Видео',
      final: 'Готово',
      wip: 'В работе',
    }
    return names[category] || category
  }

  const getStatusName = (status?: string) => {
    const names: Record<string, string> = {
      wip: 'В работе',
      ready: 'Готово',
      published: 'Опубликовано',
    }
    return names[status || ''] || 'Неизвестно'
  }

  const getStatusColor = (status?: string) => {
    const colors: Record<string, string> = {
      wip: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50',
      ready: 'bg-green-500/20 text-green-400 border-green-500/50',
      published: 'bg-blue-500/20 text-blue-400 border-blue-500/50',
    }
    return colors[status || ''] || 'bg-white/10 text-white border-white/20'
  }

  return (
    <div className="max-w-7xl mx-auto p-4 md:p-6">
      <div className={`glass-enhanced ${theme} rounded-2xl p-8 mb-8 text-white`}>
        <div className="flex items-center justify-between mb-6" data-tour="gallery-header">
          <div>
            <div className="flex items-center space-x-3 mb-2">
              <Image className="h-8 w-8 text-best-primary" />
              <h1 className={`text-3xl font-bold text-white text-readable ${theme}`}>
                Галерея результатов
              </h1>
            </div>
            <p className={`text-white/80 text-readable ${theme}`}>
              Выполненные работы команды PR-отдела
            </p>
          </div>
          
          {isCoordinator && (
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 shadow-lg shadow-best-primary/20"
            >
              {syncMutation.isPending ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <RefreshCw className="h-5 w-5" />
              )}
              <span>Синхронизировать с Drive</span>
            </button>
          )}
        </div>

        {/* Фильтры */}
        <div className="flex flex-wrap items-center gap-3 mb-6" data-tour="gallery-filters">
          <Filter className="h-5 w-5 text-white/60" />
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-4 py-2 rounded-lg transition-all ${
              selectedCategory === 'all'
                ? 'bg-best-primary text-white'
                : 'bg-white/10 text-white/70 hover:bg-white/20'
            }`}
          >
            Все
          </button>
          {['photo', 'video', 'final', 'wip'].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-lg transition-all ${
                selectedCategory === cat
                  ? 'bg-best-primary text-white'
                  : 'bg-white/10 text-white/70 hover:bg-white/20'
              }`}
            >
              {getCategoryName(cat)}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
          </div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-white/60">
            <Image className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Пока нет выполненных работ</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {items.map((item, index) => (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`p-4 rounded-lg bg-white/10 border border-white/20 hover:bg-white/15 transition-all cursor-pointer card-3d`}
                data-tour={index === 0 ? "gallery-item" : undefined}
              >
                {item.thumbnail_url && (
                  <img
                    src={item.thumbnail_url}
                    alt={item.title}
                    className="w-full h-48 object-cover rounded-lg mb-3"
                  />
                )}
                <div className="flex items-center space-x-2 mb-2">
                  {item.category === 'video' && <Film className="h-5 w-5 text-best-secondary" />}
                  {item.category === 'photo' && <Image className="h-5 w-5 text-best-primary" />}
                  <h3 className={`font-semibold text-white text-readable ${theme}`}>
                    {item.title}
                  </h3>
                </div>
                {item.description && (
                  <p className={`text-white/70 text-sm mb-3 line-clamp-2 text-readable ${theme}`}>
                    {item.description}
                  </p>
                )}
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(
                      item.status
                    )}`}
                  >
                    {getStatusName(item.status)}
                  </span>
                  {item.metrics && (
                    <div className="flex items-center space-x-3 text-white/60 text-xs">
                      {item.metrics.views !== undefined && (
                        <span className="flex items-center space-x-1">
                          <Eye className="h-3 w-3" />
                          <span>{item.metrics.views}</span>
                        </span>
                      )}
                      {item.metrics.likes !== undefined && (
                        <span className="flex items-center space-x-1">
                          <Heart className="h-3 w-3" />
                          <span>{item.metrics.likes}</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2 mb-2">
                  {item.tags?.map((tag, index) => (
                    <span
                      key={index}
                      className="px-2 py-1 bg-best-primary/20 text-best-primary rounded text-xs flex items-center space-x-1"
                    >
                      <Tag className="h-3 w-3" />
                      <span>{tag}</span>
                    </span>
                  ))}
                </div>
                <div className="flex items-center justify-between text-white/60 text-xs">
                  <div className="flex items-center space-x-1">
                    <Calendar className="h-3 w-3" />
                    <span>
                      {item.completed_at
                        ? new Date(item.completed_at).toLocaleDateString('ru-RU')
                        : new Date(item.created_at).toLocaleDateString('ru-RU')}
                    </span>
                  </div>
                  {item.creator_name && (
                    <div className="flex items-center space-x-1">
                      <User className="h-3 w-3" />
                      <span>{item.creator_name}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Модальное окно с деталями проекта */}
      {selectedItem && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedItem(null)}
        >
          <div
            className={`glass-enhanced ${theme} rounded-xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-4">
              <h2 className={`text-2xl font-bold text-white text-readable ${theme}`}>
                {selectedItem.title}
              </h2>
              <button
                onClick={() => setSelectedItem(null)}
                className="p-2 rounded-lg hover:bg-white/10 transition-all"
              >
                <span className="text-white text-2xl">×</span>
              </button>
            </div>

            {selectedItem.thumbnail_url && (
              <img
                src={selectedItem.thumbnail_url}
                alt={selectedItem.title}
                className="w-full h-64 object-cover rounded-lg mb-4"
              />
            )}

            {selectedItem.description && (
              <div className="mb-4">
                <h3 className={`text-white font-semibold mb-2 text-readable ${theme}`}>
                  Описание
                </h3>
                <p className={`text-white/80 text-readable ${theme}`}>
                  {selectedItem.description}
                </p>
              </div>
            )}

            {/* Связанная задача */}
            {selectedItem.task ? (
              <div className="mb-4 p-4 bg-white/5 rounded-lg border border-white/10">
                <h3 className="text-white font-semibold mb-2 flex items-center gap-2">
                  <CheckSquare className="h-4 w-4 text-green-400" />
                  Связанная задача
                </h3>
                <p className="font-medium text-white mb-1">{selectedItem.task.title}</p>
                {selectedItem.task.description && (
                  <p className="text-white/60 text-sm mb-2 line-clamp-3">{selectedItem.task.description}</p>
                )}
                <div className="flex flex-wrap gap-4 text-xs text-white/50">
                  {selectedItem.task.due_date && (
                    <span>Дедлайн: {new Date(selectedItem.task.due_date).toLocaleDateString('ru-RU')}</span>
                  )}
                  {selectedItem.task.completed_at && (
                    <span>Завершено: {new Date(selectedItem.task.completed_at).toLocaleDateString('ru-RU')}</span>
                  )}
                  <span className={`px-2 py-0.5 rounded-full border ${getStatusColor(selectedItem.task.status)}`}>
                    {getStatusName(selectedItem.task.status)}
                  </span>
                </div>
              </div>
            ) : (
              isCoordinator && (
                <div className="mb-4 p-4 bg-white/5 rounded-lg border border-dashed border-white/20">
                  {!isLinkingTask ? (
                    <button 
                      onClick={() => setIsLinkingTask(true)}
                      className="flex items-center gap-2 text-best-primary hover:text-best-primary/80 transition-colors text-sm font-medium"
                    >
                      <LinkIcon className="h-4 w-4" />
                      Привязать к задаче
                    </button>
                  ) : (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-medium text-white">Выберите задачу</h4>
                        <button onClick={() => setIsLinkingTask(false)} className="text-white/50 hover:text-white">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <select 
                        className="w-full bg-black/20 border border-white/10 rounded p-2 text-sm text-white focus:outline-none focus:border-best-primary"
                        value={selectedTaskId}
                        onChange={(e) => setSelectedTaskId(e.target.value)}
                      >
                        <option value="">Выберите задачу...</option>
                        {tasksData?.items?.map((task: any) => (
                          <option key={task.id} value={task.id}>
                            {task.title} ({new Date(task.created_at).toLocaleDateString()})
                          </option>
                        ))}
                      </select>
                      <button 
                        onClick={() => linkTaskMutation.mutate({ itemId: selectedItem.id, taskId: selectedTaskId })}
                        disabled={!selectedTaskId || linkTaskMutation.isPending}
                        className="w-full flex items-center justify-center gap-2 bg-best-primary text-white py-2 rounded-lg hover:bg-best-primary/80 disabled:opacity-50 text-sm"
                      >
                        {linkTaskMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                        Сохранить
                      </button>
                    </div>
                  )}
                </div>
              )
            )}

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <p className="text-white/60 text-sm mb-1">Категория</p>
                <p className={`text-white text-readable ${theme}`}>
                  {getCategoryName(selectedItem.category)}
                </p>
              </div>
              <div>
                <p className="text-white/60 text-sm mb-1">Статус</p>
                <span
                  className={`px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(
                    selectedItem.status
                  )}`}
                >
                  {getStatusName(selectedItem.status)}
                </span>
              </div>
              {selectedItem.metrics && (
                <>
                  {selectedItem.metrics.views !== undefined && (
                    <div>
                      <p className="text-white/60 text-sm mb-1">Просмотры</p>
                      <p className={`text-white text-readable ${theme}`}>
                        {selectedItem.metrics.views}
                      </p>
                    </div>
                  )}
                  {selectedItem.metrics.likes !== undefined && (
                    <div>
                      <p className="text-white/60 text-sm mb-1">Лайки</p>
                      <p className={`text-white text-readable ${theme}`}>
                        {selectedItem.metrics.likes}
                      </p>
                    </div>
                  )}
                </>
              )}
            </div>

            {selectedItem.tags && selectedItem.tags.length > 0 && (
              <div className="mb-4">
                <p className="text-white/60 text-sm mb-2">Теги</p>
                <div className="flex flex-wrap gap-2">
                  {selectedItem.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="px-3 py-1 bg-best-primary/20 text-best-primary rounded-full text-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selectedItem.files && selectedItem.files.length > 0 && (
              <div>
                <p className="text-white/60 text-sm mb-2">
                  Файлы ({selectedItem.files.length})
                </p>
                <div className="space-y-2">
                  {selectedItem.files.map((file) => (
                    <div
                      key={file.id}
                      className="p-3 bg-white/10 rounded-lg flex items-center justify-between"
                    >
                      <span className={`text-white text-readable ${theme}`}>
                        {file.file_name}
                      </span>
                      <span className="text-white/60 text-xs">{file.file_type}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
