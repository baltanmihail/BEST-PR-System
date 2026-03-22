import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Image, Loader2, Film, Filter, Eye, Heart, Tag, User, Calendar, RefreshCw, CheckSquare, Link as LinkIcon, Save, X, Plus, Upload, Trash2, ExternalLink, Play, Pencil } from 'lucide-react'
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
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createTitle, setCreateTitle] = useState('')
  const [createDescription, setCreateDescription] = useState('')
  const [createCategory, setCreateCategory] = useState<string>('final')
  const [createTags, setCreateTags] = useState('')
  const [createThumbnailUrl, setCreateThumbnailUrl] = useState('')
  const [createFiles, setCreateFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [editingField, setEditingField] = useState<'title' | 'description' | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')

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
      alert(data.message || `Добавлено: ${data.added}, обновлено: ${data.updated || 0}`)
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

  const createMutation = useMutation({
    mutationFn: (formData: { title: string; description?: string; category?: string; tags?: string; thumbnail_url?: string; files?: File[] }) =>
      galleryApi.createGalleryItem(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      setShowCreateForm(false)
      setCreateTitle('')
      setCreateDescription('')
      setCreateCategory('final')
      setCreateTags('')
      setCreateThumbnailUrl('')
      setCreateFiles([])
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка при создании элемента')
    }
  })

  const updateItemMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<GalleryItem> }) =>
      galleryApi.updateGalleryItem(id, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      setSelectedItem(updated)
      setEditingField(null)
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка обновления')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => galleryApi.deleteGalleryItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      setSelectedItem(null)
    },
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Ошибка удаления')
    }
  })

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!createTitle.trim()) return
    createMutation.mutate({
      title: createTitle,
      description: createDescription || undefined,
      category: createCategory,
      tags: createTags || undefined,
      thumbnail_url: createThumbnailUrl || undefined,
      files: createFiles.length > 0 ? createFiles : undefined,
    })
  }

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
            <div className="flex items-center space-x-2">
              <button
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className="flex items-center space-x-2 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all disabled:opacity-50 border border-white/10"
              >
                {syncMutation.isPending ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  <RefreshCw className="h-5 w-5" />
                )}
                <span className="hidden md:inline">Синхронизировать</span>
              </button>
              <button
                onClick={() => setShowCreateForm(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-best-primary text-white rounded-lg hover:bg-best-primary/80 transition-all shadow-lg shadow-best-primary/20"
              >
                <Plus className="h-5 w-5" />
                <span className="hidden md:inline">Добавить работу</span>
              </button>
            </div>
          )}
        </div>

        {/* Форма создания элемента */}
        {showCreateForm && (
          <div className="mb-6 p-6 rounded-xl bg-white/5 border border-best-primary/30">
            <div className="flex items-center justify-between mb-4">
              <h3 className={`text-lg font-bold text-white text-readable ${theme}`}>Добавить работу</h3>
              <button onClick={() => setShowCreateForm(false)} className="text-white/50 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <label className={`block text-white/80 text-sm mb-1 text-readable ${theme}`}>Название *</label>
                <input
                  type="text"
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                  required
                  placeholder="Например: Фотоотчёт LBE 2026"
                  className={`w-full bg-white/10 text-white placeholder-white/30 rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                />
              </div>
              <div>
                <label className={`block text-white/80 text-sm mb-1 text-readable ${theme}`}>Описание</label>
                <textarea
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                  placeholder="Краткое описание работы..."
                  rows={2}
                  className={`w-full bg-white/10 text-white placeholder-white/30 rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary resize-none text-readable ${theme}`}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={`block text-white/80 text-sm mb-1 text-readable ${theme}`}>Категория</label>
                  <select
                    value={createCategory}
                    onChange={(e) => setCreateCategory(e.target.value)}
                    className={`w-full bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  >
                    <option value="photo">Фото</option>
                    <option value="video">Видео</option>
                    <option value="final">Готовая работа</option>
                    <option value="wip">В работе</option>
                  </select>
                </div>
                <div>
                  <label className={`block text-white/80 text-sm mb-1 text-readable ${theme}`}>Теги</label>
                  <input
                    type="text"
                    value={createTags}
                    onChange={(e) => setCreateTags(e.target.value)}
                    placeholder="LBE, event, фото"
                    className={`w-full bg-white/10 text-white placeholder-white/30 rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                  />
                </div>
              </div>
              <div>
                <label className={`block text-white/80 text-sm mb-1 text-readable ${theme}`}>URL превью (ссылка на изображение)</label>
                <input
                  type="url"
                  value={createThumbnailUrl}
                  onChange={(e) => setCreateThumbnailUrl(e.target.value)}
                  placeholder="https://..."
                  className={`w-full bg-white/10 text-white placeholder-white/30 rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme}`}
                />
              </div>
              <div>
                <label className={`block text-white/80 text-sm mb-1 text-readable ${theme}`}>Файлы</label>
                <div 
                  className="border-2 border-dashed border-white/20 rounded-lg p-4 text-center cursor-pointer hover:border-best-primary/50 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    onChange={(e) => setCreateFiles(Array.from(e.target.files || []))}
                  />
                  {createFiles.length > 0 ? (
                    <p className="text-white/70 text-sm">{createFiles.length} файл(ов) выбрано</p>
                  ) : (
                    <div className="flex flex-col items-center text-white/40">
                      <Upload className="h-6 w-6 mb-1" />
                      <p className="text-sm">Нажмите для выбора файлов</p>
                    </div>
                  )}
                </div>
              </div>
              <button
                type="submit"
                disabled={createMutation.isPending || !createTitle.trim()}
                className="w-full flex items-center justify-center space-x-2 bg-best-primary text-white py-3 rounded-lg font-bold hover:bg-best-primary/80 transition-all disabled:opacity-50"
              >
                {createMutation.isPending ? <Loader2 className="h-5 w-5 animate-spin" /> : <Plus className="h-5 w-5" />}
                <span>{createMutation.isPending ? 'Создание...' : 'Создать'}</span>
              </button>
            </form>
          </div>
        )}

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
                onClick={() => { setSelectedItem(item); setEditingField(null) }}
                className={`p-4 rounded-lg bg-white/10 border border-white/20 hover:bg-white/15 transition-all cursor-pointer card-3d`}
                data-tour={index === 0 ? "gallery-item" : undefined}
              >
                {item.thumbnail_url ? (
                  <img src={item.thumbnail_url} alt={item.title} className="w-full h-48 object-cover rounded-lg mb-3" />
                ) : item.category === 'video' ? (
                  <div className="w-full h-48 rounded-lg mb-3 bg-black/30 flex items-center justify-center">
                    <Play className="h-12 w-12 text-white/30" />
                  </div>
                ) : null}
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
          className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={() => { setSelectedItem(null); setEditingField(null) }}
        >
          <div
            className={`glass-enhanced ${theme} rounded-xl p-6 max-w-3xl w-full max-h-[90vh] overflow-y-auto`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Заголовок */}
            <div className="flex items-start justify-between mb-4">
              {editingField === 'title' ? (
                <input
                  autoFocus
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && editTitle.trim()) {
                      updateItemMutation.mutate({ id: selectedItem.id, data: { title: editTitle.trim() } })
                    }
                    if (e.key === 'Escape') setEditingField(null)
                  }}
                  onBlur={() => {
                    if (editTitle.trim() && editTitle.trim() !== selectedItem.title) {
                      updateItemMutation.mutate({ id: selectedItem.id, data: { title: editTitle.trim() } })
                    } else setEditingField(null)
                  }}
                  className="text-2xl font-bold text-white bg-white/10 rounded-lg px-3 py-1 border border-best-primary focus:outline-none flex-1 mr-2"
                />
              ) : (
                <h2
                  className={`text-2xl font-bold text-white text-readable ${theme} ${isCoordinator ? 'cursor-pointer hover:text-best-primary transition-colors' : ''}`}
                  onClick={() => { if (isCoordinator) { setEditTitle(selectedItem.title); setEditingField('title') } }}
                  title={isCoordinator ? 'Нажмите для редактирования' : undefined}
                >
                  {selectedItem.title}
                  {isCoordinator && <Pencil className="inline w-4 h-4 ml-2 opacity-30" />}
                </h2>
              )}
              <div className="flex items-center space-x-2 flex-shrink-0 ml-2">
                {isCoordinator && (
                  <button
                    onClick={() => { if (confirm('Удалить этот элемент галереи?')) deleteMutation.mutate(selectedItem.id) }}
                    disabled={deleteMutation.isPending}
                    className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30"
                    title="Удалить"
                  >
                    {deleteMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  </button>
                )}
                <button onClick={() => { setSelectedItem(null); setEditingField(null) }} className="p-2 rounded-lg hover:bg-white/10">
                  <X className="h-5 w-5 text-white" />
                </button>
              </div>
            </div>

            {/* Видео / Изображение */}
            {selectedItem.files?.length > 0 && (() => {
              const mediaFiles = selectedItem.files.filter(f => f.file_type !== 'folder')
              const primaryFile = mediaFiles[0]
              if (!primaryFile) return null
              const isVideo = primaryFile.file_type === 'video' || primaryFile.mime_type?.startsWith('video/')
              const isImage = primaryFile.file_type === 'image' || primaryFile.mime_type?.startsWith('image/')
              const driveId = primaryFile.drive_id

              if (isVideo && driveId) {
                return (
                  <div className="mb-4 rounded-lg overflow-hidden bg-black aspect-video">
                    <iframe
                      src={`https://drive.google.com/file/d/${driveId}/preview`}
                      className="w-full h-full"
                      allow="autoplay; encrypted-media"
                      allowFullScreen
                    />
                  </div>
                )
              }
              if (isImage && selectedItem.thumbnail_url) {
                return <img src={selectedItem.thumbnail_url} alt={selectedItem.title} className="w-full max-h-96 object-contain rounded-lg mb-4 bg-black/30" />
              }
              if (selectedItem.thumbnail_url) {
                return <img src={selectedItem.thumbnail_url} alt={selectedItem.title} className="w-full max-h-96 object-contain rounded-lg mb-4 bg-black/30" />
              }
              return null
            })()}

            {/* Описание (редактируемое) */}
            <div className="mb-4">
              <h3 className="text-white/60 text-sm mb-1">Описание</h3>
              {editingField === 'description' ? (
                <textarea
                  autoFocus
                  value={editDescription}
                  onChange={e => setEditDescription(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Escape') setEditingField(null)
                  }}
                  onBlur={() => {
                    if (editDescription !== (selectedItem.description || '')) {
                      updateItemMutation.mutate({ id: selectedItem.id, data: { description: editDescription || undefined } })
                    } else setEditingField(null)
                  }}
                  rows={3}
                  className="w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-best-primary focus:outline-none resize-none"
                  placeholder="Добавьте описание..."
                />
              ) : (
                <p
                  className={`text-white/80 ${isCoordinator ? 'cursor-pointer hover:bg-white/5 rounded-lg px-2 py-1 -mx-2 transition-colors' : ''} ${!selectedItem.description ? 'italic text-white/30' : ''}`}
                  onClick={() => { if (isCoordinator) { setEditDescription(selectedItem.description || ''); setEditingField('description') } }}
                >
                  {selectedItem.description || (isCoordinator ? 'Нажмите, чтобы добавить описание...' : 'Нет описания')}
                  {isCoordinator && !selectedItem.description && <Pencil className="inline w-3 h-3 ml-1 opacity-30" />}
                </p>
              )}
            </div>

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
                  {selectedItem.task.due_date && <span>Дедлайн: {new Date(selectedItem.task.due_date).toLocaleDateString('ru-RU')}</span>}
                  {selectedItem.task.completed_at && <span>Завершено: {new Date(selectedItem.task.completed_at).toLocaleDateString('ru-RU')}</span>}
                </div>
              </div>
            ) : isCoordinator ? (
              <div className="mb-4 p-4 bg-white/5 rounded-lg border border-dashed border-white/20">
                {!isLinkingTask ? (
                  <button onClick={() => setIsLinkingTask(true)} className="flex items-center gap-2 text-best-primary hover:text-best-primary/80 text-sm font-medium">
                    <LinkIcon className="h-4 w-4" /> Привязать к задаче
                  </button>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-white">Выберите задачу</h4>
                      <button onClick={() => setIsLinkingTask(false)} className="text-white/50 hover:text-white"><X className="h-4 w-4" /></button>
                    </div>
                    <select className="w-full bg-black/20 border border-white/10 rounded p-2 text-sm text-white focus:outline-none focus:border-best-primary" value={selectedTaskId} onChange={e => setSelectedTaskId(e.target.value)}>
                      <option value="">Выберите задачу...</option>
                      {tasksData?.items?.map((task: any) => <option key={task.id} value={task.id}>{task.title}</option>)}
                    </select>
                    <button onClick={() => linkTaskMutation.mutate({ itemId: selectedItem.id, taskId: selectedTaskId })} disabled={!selectedTaskId || linkTaskMutation.isPending} className="w-full flex items-center justify-center gap-2 bg-best-primary text-white py-2 rounded-lg hover:bg-best-primary/80 disabled:opacity-50 text-sm">
                      {linkTaskMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Сохранить
                    </button>
                  </div>
                )}
              </div>
            ) : null}

            {/* Метаданные */}
            <div className="flex flex-wrap gap-3 mb-4">
              <span className="px-3 py-1 bg-white/10 rounded-full text-xs text-white/70">{getCategoryName(selectedItem.category)}</span>
              {selectedItem.creator_name && <span className="px-3 py-1 bg-white/10 rounded-full text-xs text-white/70 flex items-center gap-1"><User className="h-3 w-3" />{selectedItem.creator_name}</span>}
              <span className="px-3 py-1 bg-white/10 rounded-full text-xs text-white/70 flex items-center gap-1"><Calendar className="h-3 w-3" />{new Date(selectedItem.created_at).toLocaleDateString('ru-RU')}</span>
            </div>

            {selectedItem.tags && selectedItem.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {selectedItem.tags.map((tag, index) => <span key={index} className="px-3 py-1 bg-best-primary/20 text-best-primary rounded-full text-xs">{tag}</span>)}
              </div>
            )}

            {/* Файлы */}
            {selectedItem.files && selectedItem.files.length > 0 && (() => {
              const visibleFiles = selectedItem.files.filter(f => f.file_type !== 'folder')
              if (!visibleFiles.length) return null
              return (
              <div>
                <p className="text-white/60 text-sm mb-2">Файлы ({visibleFiles.length})</p>
                <div className="space-y-2">
                  {visibleFiles.map((file, idx) => {
                    const driveUrl = file.drive_url || (file.drive_id ? `https://drive.google.com/file/d/${file.drive_id}/view` : null)
                    const isVideo = file.file_type === 'video' || file.mime_type?.startsWith('video/')
                    const size = file.file_size ? (file.file_size > 1048576 ? `${(file.file_size / 1048576).toFixed(1)} МБ` : `${(file.file_size / 1024).toFixed(0)} КБ`) : null
                    return (
                      <div key={file.drive_id || idx} className="p-3 bg-white/10 rounded-lg flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          {isVideo ? <Play className="h-4 w-4 text-best-secondary flex-shrink-0" /> : <Image className="h-4 w-4 text-best-primary flex-shrink-0" />}
                          <span className="text-white text-sm truncate">{file.file_name}</span>
                          {size && <span className="text-white/40 text-xs flex-shrink-0">{size}</span>}
                        </div>
                        {driveUrl && (
                          <a href={driveUrl} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-blue-400 hover:text-blue-300 text-xs flex-shrink-0">
                            <ExternalLink className="h-3.5 w-3.5" /> Открыть
                          </a>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
              )
            })()}
          </div>
        </div>
      )}
    </div>
  )
}
