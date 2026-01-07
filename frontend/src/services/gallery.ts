import api from './api'

export interface GalleryFile {
  id: string
  file_name: string
  file_type: string
  drive_id: string
  version: number
  uploaded_at?: string
}

export interface GalleryItem {
  id: string
  title: string
  type: string
  completed_at: string
  files: GalleryFile[]
  files_count: number
}

export interface GalleryResponse {
  items: GalleryItem[]
  total: number
  skip: number
  limit: number
}

export const galleryApi = {
  getGallery: async (params?: {
    skip?: number
    limit?: number
    task_type?: string
  }): Promise<GalleryResponse> => {
    const response = await api.get<GalleryResponse>('/gallery', { params })
    return response.data
  },

  getTaskGallery: async (taskId: string): Promise<{
    task: {
      id: string
      title: string
      type: string
      description: string
      completed_at: string
    }
    files: GalleryFile[]
  }> => {
    const response = await api.get(`/gallery/${taskId}`)
    return response.data
  },
}
