import api from './api'

export interface TaskTemplate {
  id: string
  name: string
  description?: string
  category: string
  task_type: 'smm' | 'design' | 'channel' | 'prfr'
  priority: 'low' | 'medium' | 'high' | 'critical'
  default_description?: string
  equipment_available: boolean
  role_specific_requirements?: {
    smm?: string
    design?: string
    channel?: string
    prfr?: string
  }
  questions?: string[]
  example_project_ids?: string[]
  stages_template?: Array<{
    stage_name: string
    stage_order: number
    due_date_offset?: number
    status_color: 'green' | 'yellow' | 'red' | 'purple' | 'blue'
  }>
  drive_file_id?: string
  is_system: boolean
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export const taskTemplatesApi = {
  // Получить список шаблонов
  getTemplates: async (params?: {
    category?: string
    task_type?: string
    is_active?: boolean
  }): Promise<TaskTemplate[]> => {
    const response = await api.get<TaskTemplate[]>('/task-templates', { params })
    return response.data
  },

  // Получить шаблон по ID
  getTemplate: async (id: string): Promise<TaskTemplate> => {
    const response = await api.get<TaskTemplate>(`/task-templates/${id}`)
    return response.data
  },
}