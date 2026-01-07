import api from './api'

export interface Equipment {
  id: string
  name: string
  category: string
  status: string
  description?: string
}

export interface EquipmentRequest {
  equipment_id: string
  start_date: string
  end_date: string
  purpose: string
  task_id?: string
}

export interface EquipmentRequestResponse {
  id: string
  equipment_id: string
  equipment_name?: string
  user_id: string
  start_date: string
  end_date: string
  purpose: string
  status: string
  created_at: string
}

export const equipmentApi = {
  getEquipment: async (params?: {
    skip?: number
    limit?: number
    category?: string
    status?: string
  }) => {
    const response = await api.get('/equipment', { params })
    return response.data
  },

  getAvailableEquipment: async (params: {
    start_date: string
    end_date: string
    category?: string
  }) => {
    const response = await api.get('/equipment/available', { params })
    return response.data
  },

  getMyRequests: async (): Promise<EquipmentRequestResponse[]> => {
    const response = await api.get<EquipmentRequestResponse[]>('/equipment/requests')
    return response.data
  },

  createRequest: async (data: EquipmentRequest): Promise<EquipmentRequestResponse> => {
    const response = await api.post<EquipmentRequestResponse>('/equipment/requests', data)
    return response.data
  },
}
