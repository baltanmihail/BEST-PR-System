import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { File, Upload, Loader2, X, Image as ImageIcon, Video, FileText } from 'lucide-react'
import { tasksApi } from '../services/tasks'
import { fileUploadsApi } from '../services/fileUploads'
import { useThemeStore } from '../store/themeStore'
import { useAuthStore } from '../store/authStore'

import { TaskStage } from '../types/task'

interface TaskFilesProps {
  taskId: string
  stages?: TaskStage[]
}

interface TaskFile {
  id: string
  filename: string
  mime_type: string
  file_size: number
  drive_url: string
  drive_id: string
  description?: string
  uploaded_at: string
  uploaded_by_id: string
  stage_id?: string
}

export default function TaskFiles({ taskId, stages = [] }: TaskFilesProps) {
  const { theme } = useThemeStore()
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadDescription, setUploadDescription] = useState('')

  const isRegistered = !!user?.is_active

  // Загружаем файлы
  const { data: files, isLoading } = useQuery<TaskFile[]>({
    queryKey: ['task-files', taskId],
    queryFn: () => tasksApi.getTaskFiles(taskId),
    enabled: true, // Загружаем для всех
  })

  // Загрузка файла
  const uploadFileMutation = useMutation({
    mutationFn: ({ file, description }: { file: File; description?: string }) =>
      fileUploadsApi.uploadTaskFile(taskId, file, description),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task-files', taskId] })
      setSelectedFile(null)
      setUploadDescription('')
    },
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
    }
  }

  const handleUpload = () => {
    if (selectedFile && isRegistered) {
      uploadFileMutation.mutate({
        file: selectedFile,
        description: uploadDescription.trim() || undefined,
      })
    }
  }

  const getFileIcon = (mimeType: string) => {
    if (mimeType.startsWith('image/')) return <ImageIcon className="h-5 w-5" />
    if (mimeType.startsWith('video/')) return <Video className="h-5 w-5" />
    return <FileText className="h-5 w-5" />
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} Б`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
    return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="h-5 w-5 animate-spin text-best-primary" />
      </div>
    )
  }

  return (
    <div className="mb-4">
      <h4 className={`text-white font-semibold mb-3 flex items-center space-x-2 text-readable ${theme}`}>
        <File className="h-4 w-4" />
        <span>Файлы задачи</span>
      </h4>

      {/* Форма для загрузки файла */}
      {isRegistered && (
        <div className="mb-4 space-y-3">
          <div>
            <input
              type="file"
              id={`file-upload-${taskId}`}
              onChange={handleFileSelect}
              accept="image/*,video/*,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.rar"
              className="hidden"
            />
            <label
              htmlFor={`file-upload-${taskId}`}
              className={`flex items-center justify-center space-x-2 bg-white/10 border border-white/30 rounded-lg p-3 text-white cursor-pointer hover:bg-white/20 transition-all text-readable ${theme} text-center text-sm md:text-base touch-manipulation`}
            >
              <Upload className="h-4 w-4" />
              <span>{selectedFile ? selectedFile.name : 'Выберите файл для загрузки'}</span>
            </label>
          </div>

          {selectedFile && (
            <div className="space-y-2">
              <textarea
                value={uploadDescription}
                onChange={(e) => setUploadDescription(e.target.value)}
                placeholder="Описание файла (необязательно)..."
                className={`bg-white/10 text-white rounded-lg px-4 py-2.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-best-primary text-readable ${theme} resize-none min-h-[60px] w-full`}
                rows={2}
              />
              <div className="flex space-x-2">
                <button
                  onClick={handleUpload}
                  disabled={uploadFileMutation.isPending}
                  className="flex items-center space-x-2 bg-best-primary text-white px-4 py-2 rounded-lg hover:bg-best-primary/80 transition-all disabled:opacity-50 touch-manipulation"
                >
                  {uploadFileMutation.isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Загрузка...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="h-4 w-4" />
                      <span>Загрузить</span>
                    </>
                  )}
                </button>
                <button
                  onClick={() => {
                    setSelectedFile(null)
                    setUploadDescription('')
                  }}
                  className="flex items-center space-x-2 px-4 py-2 bg-white/10 text-white rounded-lg hover:bg-white/20 transition-all touch-manipulation"
                >
                  <X className="h-4 w-4" />
                  <span>Отмена</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Список файлов */}
      {files && files.length > 0 ? (
        <div className="space-y-2">
          {files.map((file) => (
            <a
              key={file.id}
              href={file.drive_url}
              target="_blank"
              rel="noopener noreferrer"
              className={`flex items-center space-x-3 bg-white/5 rounded-lg p-3 border border-white/10 hover:bg-white/10 transition-all text-readable ${theme}`}
            >
              <div className="text-best-primary">{getFileIcon(file.mime_type)}</div>
              <div className="flex-1 min-w-0">
                <p className={`text-white text-sm truncate text-readable ${theme}`}>{file.filename}</p>
                {file.description && (
                  <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>{file.description}</p>
                )}
                <p className={`text-white/60 text-xs mt-1 text-readable ${theme}`}>
                  {formatFileSize(file.file_size)} • {new Date(file.uploaded_at).toLocaleDateString('ru-RU')}
                </p>
              </div>
            </a>
          ))}
        </div>
      ) : (
        <p className={`text-white/60 text-sm text-readable ${theme}`}>
          {isRegistered ? 'Пока нет файлов. Загрузите первый файл!' : 'Пока нет файлов.'}
        </p>
      )}
    </div>
  )
}
