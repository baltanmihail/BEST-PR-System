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
  description?: string
  category: 'photo' | 'video' | 'final' | 'wip'
  tags?: string[]
  task_id?: string
  thumbnail_url?: string
  files: GalleryFile[]
  files_count: number
  created_by?: string
  creator_name?: string
  sort_order?: number
  created_at: string
  updated_at: string
  completed_at?: string
  status?: 'wip' | 'ready' | 'published'
  metrics?: {
    views?: number
    likes?: number
  }
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
