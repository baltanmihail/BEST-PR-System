import api from './api'

export interface FileUploadResponse {
  id: string
  filename: string
  mime_type: string
  file_size: number
  drive_url: string
  drive_id: string
  description?: string
  uploaded_at: string
  uploaded_by_id: string
}

export const fileUploadsApi = {
  // Загрузить файл к задаче (опционально к этапу)
  uploadTaskFile: async (taskId: string, file: File, description?: string, stageId?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', 'task_material')
    formData.append('task_id', taskId)
    if (stageId) {
      formData.append('stage_id', stageId)
    }
    if (description) {
      formData.append('description', description)
    }

    const response = await api.post('/file-uploads', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  },
}
