import api from './api'

export interface GalleryFile {
  id: string
  file_name: string
  file_type: string
  drive_id: string
  version: number
  uploaded_at?: string
}

export interface GalleryTaskInfo {
  id: string
  title: string
  description?: string
  status: string
  due_date?: string
  completed_at?: string
}

export interface GalleryItem {
  id: string
  title: string
  description?: string
  category: 'photo' | 'video' | 'final' | 'wip'
  tags?: string[]
  task_id?: string
  task?: GalleryTaskInfo
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
    category?: 'photo' | 'video' | 'final' | 'wip'
    task_id?: string
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

  syncFromDrive: async (): Promise<{ status: string; added: number; message: string }> => {
    const response = await api.post('/gallery/sync/drive')
    return response.data
  },

  updateGalleryItem: async (id: string, data: Partial<GalleryItem>): Promise<GalleryItem> => {
    const response = await api.put(`/gallery/${id}`, data)
    return response.data
  },

  createGalleryItem: async (data: {
    title: string
    description?: string
    category?: string
    tags?: string
    thumbnail_url?: string
    files?: File[]
  }): Promise<GalleryItem> => {
    const formData = new FormData()
    formData.append('title', data.title)
    if (data.description) formData.append('description', data.description)
    if (data.category) formData.append('category', data.category)
    if (data.tags) formData.append('tags', data.tags)
    if (data.thumbnail_url) formData.append('thumbnail_url', data.thumbnail_url)
    if (data.files) {
      data.files.forEach(file => formData.append('files', file))
    }
    const response = await api.post<GalleryItem>('/gallery', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },

  deleteGalleryItem: async (id: string): Promise<void> => {
    await api.delete(`/gallery/${id}`)
  },
}
