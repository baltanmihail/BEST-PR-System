import api from './api'

export type EquipmentCategory = 'camera' | 'lens' | 'lighting' | 'audio' | 'tripod' | 'accessories' | 'storage' | 'other'
export type EquipmentStatus = 'available' | 'rented' | 'maintenance' | 'broken'
export type EquipmentRequestStatus = 'pending' | 'approved' | 'rejected' | 'active' | 'completed' | 'cancelled'

export interface Equipment {
  id: string
  name: string
  category: EquipmentCategory
  quantity: number
  status: EquipmentStatus
  specs?: Record<string, any>
  description?: string
  image_url?: string
  created_at?: string
  updated_at?: string
}

export interface EquipmentRequest {
  equipment_id: string
  start_date: string
  end_date: string
  purpose?: string
  task_id?: string
}

export interface EquipmentRequestResponse {
  id: string
  equipment_id: string
  equipment_name?: string
  user_id: string
  start_date: string
  end_date: string
  purpose?: string
  status: EquipmentRequestStatus
  rejection_reason?: string
  created_at: string
  updated_at?: string
}

export interface EquipmentResponse {
  items: Equipment[]
  total: number
  skip: number
  limit: number
}

export interface EquipmentCreate {
  name: string
  category: EquipmentCategory
  quantity: number
  specs?: Record<string, any>
  status?: EquipmentStatus
  image_url?: string
}

export interface EquipmentUpdate {
  name?: string
  category?: EquipmentCategory
  quantity?: number
  specs?: Record<string, any>
  status?: EquipmentStatus
}

export const equipmentApi = {
  getEquipment: async (params?: {
    skip?: number
    limit?: number
    category?: string
    status?: string
  }): Promise<EquipmentResponse> => {
    const response = await api.get<EquipmentResponse>('/equipment', { params })
    return response.data
  },

  getEquipmentById: async (id: string): Promise<Equipment> => {
    const response = await api.get<Equipment>(`/equipment/${id}`)
    return response.data
  },

  getAvailableEquipment: async (params: {
    start_date: string
    end_date: string
    category?: string
  }): Promise<Equipment[]> => {
    const response = await api.get<Equipment[]>('/equipment/available', { params })
    return response.data
  },

  getMyRequests: async (): Promise<EquipmentRequestResponse[]> => {
    const response = await api.get<EquipmentRequestResponse[]>('/equipment/requests')
    return response.data
  },

  getAllRequests: async (params?: {
    skip?: number
    limit?: number
    status?: EquipmentRequestStatus
    user_id?: string
  }): Promise<{ items: EquipmentRequestResponse[]; total: number; skip: number; limit: number }> => {
    const response = await api.get('/equipment/requests/all', { params })
    return response.data
  },

  createRequest: async (data: EquipmentRequest): Promise<EquipmentRequestResponse> => {
    const response = await api.post<EquipmentRequestResponse>('/equipment/requests', data)
    return response.data
  },

  // CRUD для координаторов
  createEquipment: async (data: EquipmentCreate): Promise<Equipment> => {
    const response = await api.post<Equipment>('/equipment', data)
    return response.data
  },

  updateEquipment: async (id: string, data: EquipmentUpdate): Promise<Equipment> => {
    const response = await api.put<Equipment>(`/equipment/${id}`, data)
    return response.data
  },

  deleteEquipment: async (id: string): Promise<void> => {
    await api.delete(`/equipment/${id}`)
  },

  approveRequest: async (requestId: string): Promise<EquipmentRequestResponse> => {
    const response = await api.post<EquipmentRequestResponse>(`/equipment/requests/${requestId}/approve`)
    return response.data
  },

  rejectRequest: async (requestId: string, reason: string): Promise<EquipmentRequestResponse> => {
    const response = await api.post<EquipmentRequestResponse>(`/equipment/requests/${requestId}/reject`, null, {
      params: { reason }
    })
    return response.data
  },

  syncFromSheets: async (): Promise<any> => {
    const response = await api.post('/equipment/sync/from-sheets')
    return response.data
  },
}
