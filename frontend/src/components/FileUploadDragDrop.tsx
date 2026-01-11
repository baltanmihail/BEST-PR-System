import { useState, useRef, useCallback } from 'react'
import { Upload, X, Video, File as FileIcon, Loader2 } from 'lucide-react'
import { useThemeStore } from '../store/themeStore'

export interface FilePreview {
  file: File
  id: string
  preview?: string
  isImage: boolean
  isVideo: boolean
}

interface FileUploadDragDropProps {
  files: FilePreview[]
  onFilesChange: (files: FilePreview[]) => void
  maxFiles?: number
  maxSizeMB?: number
  disabled?: boolean
  acceptedTypes?: string[]
}

export default function FileUploadDragDrop({
  files,
  onFilesChange,
  maxFiles = 10,
  maxSizeMB = 100,
  disabled = false,
  acceptedTypes = ['image/*', 'video/*']
}: FileUploadDragDropProps) {
  const { theme } = useThemeStore()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  const generateId = () => Math.random().toString(36).substring(2, 9)

  const validateFile = (file: File): string | null => {
    // Проверка размера
    const maxSizeBytes = maxSizeMB * 1024 * 1024
    if (file.size > maxSizeBytes) {
      return `Файл "${file.name}" слишком большой (максимум ${maxSizeMB} МБ)`
    }

    // Проверка типа (если указаны acceptedTypes)
    if (acceptedTypes.length > 0) {
      const isValidType = acceptedTypes.some(type => {
        if (type.endsWith('/*')) {
          const category = type.split('/')[0]
          return file.type.startsWith(category + '/')
        }
        return file.type === type
      })
      if (!isValidType) {
        return `Файл "${file.name}" имеет недопустимый тип (разрешены: ${acceptedTypes.join(', ')})`
      }
    }

    return null
  }

  const createPreview = (file: File): Promise<FilePreview> => {
    return new Promise((resolve) => {
      const id = generateId()
      const isImage = file.type.startsWith('image/')
      const isVideo = file.type.startsWith('video/')

      if (isImage) {
        const reader = new FileReader()
        reader.onload = (e) => {
          resolve({
            file,
            id,
            preview: e.target?.result as string,
            isImage: true,
            isVideo: false
          })
        }
        reader.onerror = () => {
          resolve({ file, id, isImage: true, isVideo: false })
        }
        reader.readAsDataURL(file)
      } else if (isVideo) {
        // Для видео создаём превью из первого кадра
        const video = document.createElement('video')
        video.preload = 'metadata'
        video.onloadedmetadata = () => {
          video.currentTime = 0.1
          video.onseeked = () => {
            const canvas = document.createElement('canvas')
            canvas.width = video.videoWidth
            canvas.height = video.videoHeight
            const ctx = canvas.getContext('2d')
            if (ctx) {
              ctx.drawImage(video, 0, 0)
              const preview = canvas.toDataURL()
              URL.revokeObjectURL(video.src)
              resolve({
                file,
                id,
                preview,
                isImage: false,
                isVideo: true
              })
            } else {
              URL.revokeObjectURL(video.src)
              resolve({ file, id, isImage: false, isVideo: true })
            }
          }
          video.onerror = () => {
            URL.revokeObjectURL(video.src)
            resolve({ file, id, isImage: false, isVideo: true })
          }
        }
        video.onerror = () => {
          URL.revokeObjectURL(video.src)
          resolve({ file, id, isImage: false, isVideo: true })
        }
        video.src = URL.createObjectURL(file)
      } else {
        resolve({ file, id, isImage: false, isVideo: false })
      }
    })
  }

  const handleFiles = useCallback(async (newFiles: FileList | File[]) => {
    if (disabled || uploading) return

    const fileArray = Array.from(newFiles)
    
    // Проверка лимита
    if (files.length + fileArray.length > maxFiles) {
      alert(`Можно загрузить максимум ${maxFiles} файлов`)
      return
    }

    // Валидация файлов
    const errors: string[] = []
    const validFiles: File[] = []
    
    for (const file of fileArray) {
      const error = validateFile(file)
      if (error) {
        errors.push(error)
      } else {
        validFiles.push(file)
      }
    }

    if (errors.length > 0) {
      alert(errors.join('\n'))
    }

    if (validFiles.length === 0) return

    // Создаём превью
    setUploading(true)
    try {
      const previews = await Promise.all(validFiles.map(createPreview))
      onFilesChange([...files, ...previews])
    } finally {
      setUploading(false)
    }
  }, [files, onFilesChange, maxFiles, disabled, uploading, acceptedTypes, maxSizeMB])

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled && !uploading) {
      setIsDragging(true)
    }
  }, [disabled, uploading])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    if (disabled || uploading) return

    const droppedFiles = e.dataTransfer.files
    if (droppedFiles.length > 0) {
      handleFiles(droppedFiles)
    }
  }, [disabled, uploading, handleFiles])

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files)
    }
    // Сбрасываем input, чтобы можно было выбрать тот же файл снова
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [handleFiles])

  const removeFile = useCallback((id: string) => {
    if (disabled || uploading) return
    onFilesChange(files.filter(f => f.id !== id))
  }, [files, onFilesChange, disabled, uploading])

  const moveFile = useCallback((fromIndex: number, toIndex: number) => {
    if (disabled || uploading) return
    const newFiles = [...files]
    const [moved] = newFiles.splice(fromIndex, 1)
    newFiles.splice(toIndex, 0, moved)
    onFilesChange(newFiles)
  }, [files, onFilesChange, disabled, uploading])

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' Б'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' КБ'
    return (bytes / (1024 * 1024)).toFixed(1) + ' МБ'
  }

  return (
    <div className="space-y-4">
      {/* Зона drag & drop */}
      <div
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && !uploading && fileInputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-all duration-200
          ${isDragging 
            ? 'border-best-primary bg-best-primary/20' 
            : 'border-white/30 bg-white/5 hover:bg-white/10 hover:border-white/50'
          }
          ${disabled || uploading ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={acceptedTypes.join(',')}
          onChange={handleFileInput}
          disabled={disabled || uploading}
          className="hidden"
        />
        
        {uploading ? (
          <div className="flex flex-col items-center space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-best-primary" />
            <p className={`text-white/60 text-sm text-readable ${theme}`}>Обработка файлов...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-3">
            <Upload className={`h-8 w-8 ${isDragging ? 'text-best-primary' : 'text-white/60'}`} />
            <div>
              <p className={`text-white font-medium text-readable ${theme}`}>
                {isDragging ? 'Отпустите для загрузки' : 'Перетащите файлы сюда или нажмите для выбора'}
              </p>
              <p className={`text-white/60 text-sm mt-1 text-readable ${theme}`}>
                Поддерживаются изображения и видео (макс. {maxSizeMB} МБ)
              </p>
              <p className={`text-white/40 text-xs mt-1 text-readable ${theme}`}>
                Загружено: {files.length} / {maxFiles}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Превью загруженных файлов */}
      {files.length > 0 && (
        <div className="space-y-3">
          <p className={`text-white/80 text-sm font-medium text-readable ${theme}`}>
            Загруженные файлы (первое изображение будет использовано как превью):
          </p>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {files.map((filePreview, index) => (
              <div
                key={filePreview.id}
                className={`
                  relative group bg-white/5 rounded-lg overflow-hidden border
                  ${index === 0 && filePreview.isImage ? 'border-best-primary border-2' : 'border-white/20'}
                `}
              >
                {/* Кнопка удаления */}
                {!disabled && !uploading && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      removeFile(filePreview.id)
                    }}
                    className="absolute top-2 right-2 z-10 p-1 bg-red-500/80 hover:bg-red-500 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                    aria-label="Удалить файл"
                  >
                    <X className="h-4 w-4 text-white" />
                  </button>
                )}

                {/* Индикатор основного (первого) файла */}
                {index === 0 && filePreview.isImage && (
                  <div className="absolute top-2 left-2 z-10 px-2 py-1 bg-best-primary/80 rounded text-xs text-white font-medium">
                    Превью
                  </div>
                )}

                {/* Превью */}
                <div className="aspect-square bg-white/5 flex items-center justify-center overflow-hidden">
                  {filePreview.isImage && filePreview.preview ? (
                    <img
                      src={filePreview.preview}
                      alt={filePreview.file.name}
                      className="w-full h-full object-cover"
                    />
                  ) : filePreview.isVideo && filePreview.preview ? (
                    <div className="relative w-full h-full">
                      <img
                        src={filePreview.preview}
                        alt={filePreview.file.name}
                        className="w-full h-full object-cover"
                      />
                      <Video className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 h-8 w-8 text-white drop-shadow-lg" />
                    </div>
                  ) : (
                    <FileIcon className="h-8 w-8 text-white/40" />
                  )}
                </div>

                {/* Информация о файле */}
                <div className="p-2">
                  <p className={`text-white text-xs truncate text-readable ${theme}`} title={filePreview.file.name}>
                    {filePreview.file.name}
                  </p>
                  <p className={`text-white/60 text-xs text-readable ${theme}`}>
                    {formatFileSize(filePreview.file.size)}
                  </p>
                </div>

                {/* Кнопки перемещения (если больше 1 файла) */}
                {files.length > 1 && !disabled && !uploading && (
                  <div className="absolute bottom-2 left-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {index > 0 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          moveFile(index, index - 1)
                        }}
                        className="flex-1 px-2 py-1 bg-white/20 hover:bg-white/30 rounded text-xs text-white"
                        title="Переместить влево (сделать основным)"
                      >
                        ←
                      </button>
                    )}
                    {index < files.length - 1 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          moveFile(index, index + 1)
                        }}
                        className="flex-1 px-2 py-1 bg-white/20 hover:bg-white/30 rounded text-xs text-white"
                        title="Переместить вправо"
                      >
                        →
                      </button>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
