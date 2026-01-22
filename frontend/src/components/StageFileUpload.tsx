import { useState, useRef } from 'react'
import { Check, AlertCircle, Paperclip } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { fileUploadsApi } from '../services/fileUploads'

interface StageFileUploadProps {
  taskId: string
  stageId: string // ID этапа (UUID строка)
  stageName: string
  onUploadSuccess?: () => void
}

export default function StageFileUpload({ taskId, stageId, stageName, onUploadSuccess }: StageFileUploadProps) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)

  const uploadFileMutation = useMutation({
    mutationFn: (file: File) => 
      fileUploadsApi.uploadTaskFile(taskId, file, `Файл для этапа: ${stageName}`, stageId),
    onSuccess: () => {
      // Обновляем файлы задачи
      queryClient.invalidateQueries({ queryKey: ['task-files', taskId] })
      // Обновляем саму задачу (чтобы обновился статус этапа)
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      
      if (onUploadSuccess) onUploadSuccess()
      setError(null)
      
      // Сбрасываем статус успеха через 2 секунды
      setTimeout(() => uploadFileMutation.reset(), 2000)
    },
    onError: (err: any) => {
      setError(err?.message || 'Ошибка загрузки')
      setTimeout(() => setError(null), 3000)
    }
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadFileMutation.mutate(file)
    }
    // Сбрасываем input, чтобы можно было выбрать тот же файл
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="relative inline-block">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        className="hidden"
        disabled={uploadFileMutation.isPending}
      />
      
      <button
        onClick={handleClick}
        disabled={uploadFileMutation.isPending}
        className={`p-1.5 rounded-lg transition-colors ${
          uploadFileMutation.isPending 
            ? 'bg-white/10 cursor-not-allowed' 
            : error 
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
              : uploadFileMutation.isSuccess
                ? 'bg-green-500/20 text-green-400'
                : 'bg-white/10 text-white/70 hover:bg-white/20 hover:text-white'
        }`}
        title={`Загрузить файл для этапа "${stageName}"`}
      >
        {uploadFileMutation.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : error ? (
          <AlertCircle className="h-4 w-4" />
        ) : uploadFileMutation.isSuccess ? (
          <Check className="h-4 w-4" />
        ) : (
          <Paperclip className="h-4 w-4" />
        )}
      </button>
    </div>
  )
}
