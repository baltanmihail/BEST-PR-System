import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Loader2, AlertCircle, X, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQueryClient, useQuery } from '@tanstack/react-query'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'
import { tasksApi } from '../services/tasks'
import { taskTemplatesApi } from '../services/taskTemplates'
import { galleryApi } from '../services/gallery'
import { fileUploadsApi } from '../services/fileUploads'
import FileUploadDragDrop, { type FilePreview } from '../components/FileUploadDragDrop'
import { TaskCreate, TaskType, TaskPriority, TaskStageCreate } from '../types/task'

export default function CreateTask() {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [taskType, setTaskType] = useState<TaskType>('smm')
  const [priority, setPriority] = useState<TaskPriority>('medium')
  const [dueDate, setDueDate] = useState('')
  const [equipmentAvailable, setEquipmentAvailable] = useState(false)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [stages, setStages] = useState<TaskStageCreate[]>([])
  const [roleRequirements, setRoleRequirements] = useState<{ smm?: string; design?: string; channel?: string; prfr?: string }>({})
  const [exampleProjectIds, setExampleProjectIds] = useState<string[]>([])
  const [uploadedFiles, setUploadedFiles] = useState<FilePreview[]>([])
  const [questions, setQuestions] = useState<string[]>([''])
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number } | null>(null)

  // Проверяем, является ли пользователь координатором
  const roleStr = typeof user?.role === 'string' ? user.role : String(user?.role || '')
  const isCoordinator = user && (roleStr.includes('coordinator') || roleStr === 'vp4pr')

  // Загружаем шаблоны задач
  const { data: templates, isLoading: templatesLoading } = useQuery({
    queryKey: ['task-templates', taskType],
    queryFn: () => taskTemplatesApi.getTemplates({ task_type: taskType, is_active: true }),
    enabled: isCoordinator === true,
  })

  // Загружаем элементы галереи для примеров работ
  const { data: galleryData } = useQuery({
    queryKey: ['gallery', 'examples'],
    queryFn: () => galleryApi.getGallery({ limit: 100 }),
    enabled: isCoordinator === true,
  })

  // Загрузка шаблона и заполнение формы
  const handleTemplateChange = async (templateId: string) => {
    if (!templateId) {
      setSelectedTemplateId('')
      return
    }
    
    try {
      const template = await taskTemplatesApi.getTemplate(templateId)
      setSelectedTemplateId(templateId)
      
      // Заполняем поля из шаблона
      if (template.default_description) setDescription(template.default_description)
      setPriority(template.priority)
      setEquipmentAvailable(template.equipment_available)
      if (template.role_specific_requirements) setRoleRequirements(template.role_specific_requirements)
      if (template.example_project_ids) setExampleProjectIds(template.example_project_ids)
      if (template.questions) setQuestions(template.questions.length > 0 ? template.questions : [''])
      
      // Заполняем этапы из шаблона (если есть due_date, вычисляем дату относительно dueDate)
      if (template.stages_template && template.stages_template.length > 0) {
        const baseDate = dueDate ? new Date(dueDate) : new Date()
        const templateStages: TaskStageCreate[] = template.stages_template.map((stage, index) => {
          let stageDueDate: string | undefined
          if (stage.due_date_offset !== undefined && dueDate) {
            const date = new Date(baseDate)
            date.setDate(date.getDate() - stage.due_date_offset)
            stageDueDate = date.toISOString()
          }
          return {
            stage_name: stage.stage_name,
            stage_order: stage.stage_order || index + 1,
            due_date: stageDueDate,
            status_color: stage.status_color || 'green',
          }
        })
        setStages(templateStages)
      }
    } catch (err) {
      console.error('Ошибка загрузки шаблона:', err)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!title.trim()) {
      setError('Пожалуйста, укажите название задачи')
      return
    }

    if (!taskType) {
      setError('Пожалуйста, выберите тип задачи')
      return
    }

    setIsSubmitting(true)

    // Подготовка этапов
    const validStages = stages
      .filter(s => s.stage_name.trim())
      .map((stage, index) => ({
        ...stage,
        stage_order: stage.stage_order || index + 1,
      }))

    // Подготовка ТЗ по ролям (только непустые значения)
    const validRoleRequirements: { [key: string]: string } = {}
    // Для многозадачной задачи сохраняем все роли, для остальных - только выбранную
    if (taskType === 'multitask') {
      if (roleRequirements.smm?.trim()) validRoleRequirements.smm = roleRequirements.smm.trim()
      if (roleRequirements.design?.trim()) validRoleRequirements.design = roleRequirements.design.trim()
      if (roleRequirements.channel?.trim()) validRoleRequirements.channel = roleRequirements.channel.trim()
      if (roleRequirements.prfr?.trim()) validRoleRequirements.prfr = roleRequirements.prfr.trim()
    } else {
      // Для обычных типов - только выбранная роль
      const roleKey = taskType
      if (roleRequirements[roleKey as keyof typeof roleRequirements]?.trim()) {
        validRoleRequirements[roleKey] = roleRequirements[roleKey as keyof typeof roleRequirements]!.trim()
      }
    }

    // Подготовка вопросов (только непустые)
    const validQuestions = questions.filter(q => q.trim()).map(q => q.trim())

    const taskData: TaskCreate = {
      title: title.trim(),
      description: description.trim() || undefined,
      type: taskType,
      priority: priority,
      due_date: dueDate ? new Date(dueDate).toISOString() : undefined,
      equipment_available: taskType === 'channel' ? equipmentAvailable : false,
      stages: validStages.length > 0 ? validStages : undefined,
      role_specific_requirements: Object.keys(validRoleRequirements).length > 0 ? validRoleRequirements : undefined,
      example_project_ids: exampleProjectIds.length > 0 ? exampleProjectIds : undefined,
      questions: validQuestions.length > 0 ? validQuestions : undefined,
    }

    try {
      // 1. Создаем задачу
      const task = await tasksApi.createTask(taskData)

      // 2. Загружаем файлы (если есть)
      if (uploadedFiles.length > 0) {
        setUploadProgress({ current: 0, total: uploadedFiles.length })
        
        // Загружаем файлы последовательно, чтобы обновлять прогресс
        for (let i = 0; i < uploadedFiles.length; i++) {
          try {
            await fileUploadsApi.uploadTaskFile(task.id, uploadedFiles[i].file)
            setUploadProgress({ current: i + 1, total: uploadedFiles.length })
          } catch (err) {
            console.error(`Ошибка загрузки файла ${uploadedFiles[i].file.name}:`, err)
            // Не прерываем процесс из-за одного файла, но можно собрать ошибки
          }
        }
      }

      // 3. Успех и редирект
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      navigate('/tasks')
      
    } catch (err: any) {
      console.error('Ошибка при создании задачи:', err)
      setError(err?.response?.data?.detail || err?.message || 'Ошибка при создании задачи')
      setIsSubmitting(false)
      setUploadProgress(null)
    }
  }

  // Если пользователь не координатор, показываем сообщение об ошибке
  if (!isCoordinator) {
    return (
      <div className="max-w-4xl mx-auto p-4 md:p-6">
        <div className={`glass-enhanced ${theme} rounded-xl p-6 text-center`}>
          <AlertCircle className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <p className={`text-white text-xl text-readable ${theme}`}>
            Доступ запрещён. Только координаторы могут создавать задачи.
          </p>
          <Link
            to="/tasks"
            className="mt-4 inline-flex items-center space-x-2 text-best-primary hover:text-best-primary/80 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Вернуться к задачам</span>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6">
      {/* Заголовок */}
      <div className="flex items-center space-x-4 mb-6">
        <Link
          to="/tasks"
          className="p-2 rounded-lg hover:bg-white/10 transition-colors touch-manipulation"
          aria-label="Назад к задачам"
        >
          <ArrowLeft className="h-5 w-5 text-white" />
        </Link>
        <div>
          <h1 className={`text-2xl md:text-3xl font-bold text-white flex items-center space-x-2 text-readable ${theme}`}>
            <Plus className="h-6 w-6 md:h-8 md:w-8 text-white" style={{ 
              filter: 'drop-shadow(0 0 8px rgba(30, 136, 229, 0.8)) drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3))'
            }} />
            <span>Создать задачу</span>
          </h1>
          <p className={`text-white/60 mt-1 text-sm md:text-base text-readable ${theme}`}>
            Заполните форму для создания новой задачи
          </p>
        </div>
      </div>

      {/* Форма */}
      <form onSubmit={handleSubmit} className={`glass-enhanced ${theme} rounded-xl p-6 md:p-8`}>
        {/* Ошибка */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500/50 rounded-lg flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
            <p className={`text-red-400 text-sm text-readable ${theme}`}>{error}</p>
          </div>
        )}

        {/* Успех */}
        {/*
        <div className="mb-6 p-4 bg-green-500/20 border border-green-500/50 rounded-lg flex items-start space-x-3">
          <CheckCircle2 className="h-5 w-5 text-green-400 flex-shrink-0 mt-0.5" />
          <p className={`text-green-400 text-sm text-readable ${theme}`}>
            Задача успешно создана!
          </p>
        </div>
        */}

        <div className="space-y-6">
          {/* Название задачи */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Название задачи <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Введите название задачи"
              required
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border ${
                error && !title.trim() ? 'border-red-500' : 'border-white/20'
              } focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40`}
              disabled={isSubmitting}
            />
          </div>

          {/* Тип задачи */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Тип задачи <span className="text-red-400">*</span>
            </label>
            <select
              value={taskType}
              onChange={(e) => {
                const newType = e.target.value as TaskType
                setTaskType(newType)
                // Сбрасываем equipment_available при смене типа
                if (newType !== 'channel') {
                  setEquipmentAvailable(false)
                }
                // При смене типа задачи (если не multitask) очищаем ТЗ других ролей
                if (newType !== 'multitask') {
                  const clearedRequirements: { [key: string]: string } = {}
                  clearedRequirements[newType] = roleRequirements[newType as keyof typeof roleRequirements] || ''
                  setRoleRequirements(clearedRequirements)
                }
              }}
              required
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
              disabled={isSubmitting}
            >
              <option value="smm">SMM</option>
              <option value="design">Design</option>
              <option value="channel">Channel</option>
              <option value="prfr">PR-FR</option>
              <option value="multitask">Многозадачная</option>
            </select>
          </div>

          {/* Описание */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Описание
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Описание задачи (опционально)"
              rows={6}
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 resize-y`}
              disabled={isSubmitting}
            />
          </div>

          {/* Приоритет */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Приоритет
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value as TaskPriority)}
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
              disabled={isSubmitting}
            >
              <option value="low">Низкий</option>
              <option value="medium">Средний</option>
              <option value="high">Высокий</option>
              <option value="critical">Критический</option>
            </select>
          </div>

          {/* Дедлайн */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Дедлайн
            </label>
            <input
              type="datetime-local"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&::-webkit-calendar-picker-indicator]:filter [&::-webkit-calendar-picker-indicator]:invert`}
              disabled={isSubmitting}
            />
          </div>

          {/* Оборудование доступно (только для Channel) */}
          {taskType === 'channel' && (
            <div>
              <label className={`flex items-center space-x-3 cursor-pointer text-readable ${theme}`}>
                <input
                  type="checkbox"
                  checked={equipmentAvailable}
                  onChange={(e) => setEquipmentAvailable(e.target.checked)}
                  className="w-5 h-5 rounded border-white/20 bg-white/10 text-best-primary focus:ring-2 focus:ring-best-primary cursor-pointer"
                  disabled={isSubmitting}
                />
                <span className="text-white text-sm font-medium">
                  Оборудование доступно для этой задачи
                </span>
              </label>
              <p className={`text-white/60 text-xs mt-1 ml-8 text-readable ${theme}`}>
                Если отмечено, пользователи смогут запросить оборудование для выполнения этой задачи
              </p>
            </div>
          )}

          {/* Выбор шаблона */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Шаблон задачи (опционально)
            </label>
            <select
              value={selectedTemplateId}
              onChange={(e) => handleTemplateChange(e.target.value)}
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white touch-manipulation`}
              disabled={isSubmitting || templatesLoading}
            >
              <option value="">Не использовать шаблон</option>
              {templates?.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
            <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
              Выберите шаблон, чтобы автоматически заполнить поля формы
            </p>
          </div>

          {/* Загрузка файлов */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Фото и видео для задачи
            </label>
            <FileUploadDragDrop
              files={uploadedFiles}
              onFilesChange={setUploadedFiles}
              maxFiles={10}
              maxSizeMB={100}
              disabled={isSubmitting}
              acceptedTypes={['image/*', 'video/*']}
            />
            <p className={`text-white/60 text-xs mt-2 text-readable ${theme}`}>
              Перетащите файлы в область или нажмите для выбора. Первое изображение будет использовано как превью карточки задачи.
            </p>
          </div>

          {/* ТЗ по ролям */}
          <div>
            <label className={`block text-white mb-3 text-sm font-medium text-readable ${theme}`}>
              Техническое задание по ролям
            </label>
            {taskType === 'multitask' ? (
              // Для многозадачной задачи - показываем все роли
              <div className="space-y-4">
                <div>
                  <label className={`block text-white/80 mb-2 text-xs text-readable ${theme}`}>SMM</label>
                  <textarea
                    value={roleRequirements.smm || ''}
                    onChange={(e) => setRoleRequirements({ ...roleRequirements, smm: e.target.value })}
                    placeholder="ТЗ для SMM (опционально)"
                    rows={3}
                    className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 resize-y text-sm`}
                    disabled={isSubmitting}
                  />
                </div>
                <div>
                  <label className={`block text-white/80 mb-2 text-xs text-readable ${theme}`}>Design</label>
                  <textarea
                    value={roleRequirements.design || ''}
                    onChange={(e) => setRoleRequirements({ ...roleRequirements, design: e.target.value })}
                    placeholder="ТЗ для Design (опционально)"
                    rows={3}
                    className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 resize-y text-sm`}
                    disabled={isSubmitting}
                  />
                </div>
                <div>
                  <label className={`block text-white/80 mb-2 text-xs text-readable ${theme}`}>Channel</label>
                  <textarea
                    value={roleRequirements.channel || ''}
                    onChange={(e) => setRoleRequirements({ ...roleRequirements, channel: e.target.value })}
                    placeholder="ТЗ для Channel (опционально)"
                    rows={3}
                    className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 resize-y text-sm`}
                    disabled={isSubmitting}
                  />
                </div>
                <div>
                  <label className={`block text-white/80 mb-2 text-xs text-readable ${theme}`}>PR-FR</label>
                  <textarea
                    value={roleRequirements.prfr || ''}
                    onChange={(e) => setRoleRequirements({ ...roleRequirements, prfr: e.target.value })}
                    placeholder="ТЗ для PR-FR (опционально)"
                    rows={3}
                    className={`w-full bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 resize-y text-sm`}
                    disabled={isSubmitting}
                  />
                </div>
              </div>
            ) : (
              // Для обычных типов - показываем только ТЗ для выбранной роли
              <div>
                <label className={`block text-white/80 mb-2 text-xs text-readable ${theme}`}>
                  {taskType === 'smm' ? 'SMM' : 
                   taskType === 'design' ? 'Design' : 
                   taskType === 'channel' ? 'Channel' : 
                   taskType === 'prfr' ? 'PR-FR' : 'ТЗ для роли'}
                </label>
                <textarea
                  value={roleRequirements[taskType] || ''}
                  onChange={(e) => setRoleRequirements({ ...roleRequirements, [taskType]: e.target.value })}
                  placeholder={`ТЗ для ${taskType === 'smm' ? 'SMM' : taskType === 'design' ? 'Design' : taskType === 'channel' ? 'Channel' : taskType === 'prfr' ? 'PR-FR' : taskType} (опционально)`}
                  rows={6}
                  className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 resize-y`}
                  disabled={isSubmitting}
                />
              </div>
            )}
          </div>

          {/* Этапы задачи */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className={`block text-white text-sm font-medium text-readable ${theme}`}>
                Этапы задачи
              </label>
              <button
                type="button"
                onClick={() => {
                  setStages([...stages, { stage_name: '', stage_order: stages.length + 1, status_color: 'green' }])
                }}
                className="flex items-center space-x-1 text-best-primary hover:text-best-primary/80 text-sm font-medium"
                disabled={isSubmitting}
              >
                <Plus className="h-4 w-4" />
                <span>Добавить этап</span>
              </button>
            </div>
            <div className="space-y-3">
              {stages.map((stage, index) => (
                <div key={index} className={`bg-white/5 rounded-lg p-4 border border-white/10`}>
                  <div className="flex items-start justify-between mb-3">
                    <span className={`text-white/60 text-xs text-readable ${theme}`}>Этап {index + 1}</span>
                    <button
                      type="button"
                      onClick={() => {
                        const newStages = stages.filter((_, i) => i !== index)
                        setStages(newStages.map((s, i) => ({ ...s, stage_order: i + 1 })))
                      }}
                      className="text-red-400 hover:text-red-300"
                      disabled={isSubmitting}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className={`block text-white/80 mb-1 text-xs text-readable ${theme}`}>Название этапа *</label>
                      <input
                        type="text"
                        value={stage.stage_name}
                        onChange={(e) => {
                          const newStages = [...stages]
                          newStages[index] = { ...stage, stage_name: e.target.value }
                          setStages(newStages)
                        }}
                        placeholder="Название этапа"
                        className={`w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 text-sm`}
                        disabled={isSubmitting}
                      />
                    </div>
                    <div>
                      <label className={`block text-white/80 mb-1 text-xs text-readable ${theme}`}>Дедлайн этапа</label>
                      <input
                        type="datetime-local"
                        value={stage.due_date ? new Date(stage.due_date).toISOString().slice(0, 16) : ''}
                        onChange={(e) => {
                          const newStages = [...stages]
                          newStages[index] = { ...stage, due_date: e.target.value ? new Date(e.target.value).toISOString() : undefined }
                          setStages(newStages)
                        }}
                        className={`w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} text-sm [&::-webkit-calendar-picker-indicator]:filter [&::-webkit-calendar-picker-indicator]:invert`}
                        disabled={isSubmitting}
                      />
                    </div>
                    <div>
                      <label className={`block text-white/80 mb-1 text-xs text-readable ${theme}`}>Цвет статуса</label>
                      <select
                        value={stage.status_color || 'green'}
                        onChange={(e) => {
                          const newStages = [...stages]
                          newStages[index] = { ...stage, status_color: e.target.value as any }
                          setStages(newStages)
                        }}
                        className={`w-full bg-white/10 text-white rounded-lg px-3 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white text-sm`}
                        disabled={isSubmitting}
                      >
                        <option value="green">Зелёный</option>
                        <option value="yellow">Жёлтый</option>
                        <option value="red">Красный</option>
                        <option value="purple">Фиолетовый</option>
                        <option value="blue">Синий</option>
                      </select>
                    </div>
                  </div>
                </div>
              ))}
              {stages.length === 0 && (
                <p className={`text-white/40 text-sm text-center py-4 text-readable ${theme}`}>
                  Этапы не добавлены. Нажмите "Добавить этап", чтобы создать этап задачи.
                </p>
              )}
            </div>
          </div>

          {/* Примеры работ из галереи */}
          <div>
            <label className={`block text-white mb-2 text-sm font-medium text-readable ${theme}`}>
              Примеры работ из галереи
            </label>
            <select
              multiple
              value={exampleProjectIds}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions, option => option.value)
                setExampleProjectIds(selected)
              }}
              className={`w-full bg-white/10 text-white rounded-lg px-4 py-3 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} [&>option]:bg-gray-800 [&>option]:text-white min-h-[120px]`}
              disabled={isSubmitting}
              size={5}
            >
              {galleryData?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title} {item.category && `(${item.category})`}
                </option>
              ))}
            </select>
            <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
              Удерживайте Ctrl (Cmd на Mac), чтобы выбрать несколько работ. Выбрано: {exampleProjectIds.length}
            </p>
          </div>

          {/* Вопросы */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <label className={`block text-white text-sm font-medium text-readable ${theme}`}>
                Вопросы по задаче
              </label>
              <button
                type="button"
                onClick={() => setQuestions([...questions, ''])}
                className="flex items-center space-x-1 text-best-primary hover:text-best-primary/80 text-sm font-medium"
                disabled={isSubmitting}
              >
                <Plus className="h-4 w-4" />
                <span>Добавить вопрос</span>
              </button>
            </div>
            <div className="space-y-2">
              {questions.map((question, index) => (
                <div key={index} className="flex items-start space-x-2">
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => {
                      const newQuestions = [...questions]
                      newQuestions[index] = e.target.value
                      setQuestions(newQuestions)
                    }}
                    placeholder={`Вопрос ${index + 1}`}
                    className={`flex-1 bg-white/10 text-white rounded-lg px-4 py-2 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} placeholder-white/40 text-sm`}
                    disabled={isSubmitting}
                  />
                  {questions.length > 1 && (
                    <button
                      type="button"
                      onClick={() => {
                        const newQuestions = questions.filter((_, i) => i !== index)
                        setQuestions(newQuestions.length > 0 ? newQuestions : [''])
                      }}
                      className="text-red-400 hover:text-red-300 p-2"
                      disabled={isSubmitting}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Кнопки */}
          <div className="flex flex-col sm:flex-row gap-4 pt-4">
            <button
              type="submit"
              disabled={isSubmitting || !title.trim()}
              className="flex-1 bg-best-primary hover:bg-best-primary/90 text-white font-medium py-3 px-6 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  {uploadProgress ? (
                    <span>Загрузка файлов ({uploadProgress.current}/{uploadProgress.total})...</span>
                  ) : (
                    <span>Создание задачи...</span>
                  )}
                </>
              ) : (
                <>
                  <Plus className="h-5 w-5" />
                  <span>Создать задачу</span>
                </>
              )}
            </button>
            <Link
              to="/tasks"
              className={`flex-1 sm:flex-none bg-white/10 hover:bg-white/20 text-white font-medium py-3 px-6 rounded-lg transition-all text-center ${isSubmitting ? 'opacity-50 pointer-events-none' : ''}`}
            >
              Отмена
            </Link>
          </div>
        </div>
      </form>
    </div>
  )
}