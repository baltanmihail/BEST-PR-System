import api from './api'

export type CalendarView = 'month' | 'week' | 'timeline' | 'semester'
export type CalendarRole = 'smm' | 'design' | 'channel' | 'prfr'
export type DetailLevel = 'compact' | 'normal' | 'detailed'

export interface CalendarTask {
  id: string
  title: string
  type: string
  status: string
  priority: string
  due_date?: string
  start_date?: string
  stages?: Array<{
    id: string
    stage_name: string
    due_date?: string
    status: string
  }>
  assignments?: Array<{
    user_id: string
    user_name: string
  }>
  equipment_requests?: Array<{
    equipment_id: string
    equipment_name: string
    start_date: string
    end_date: string
  }>
}

export interface CalendarResponse {
  view: 'month' | 'week' | 'timeline' | 'semester'
  // Для month/week
  days?: Array<{
    date: string
    tasks?: any[]
    stages?: any[]
    equipment?: any[]
    items?: any[]
  }>
  // Для timeline
  items?: any[]
  // Для gantt
  tasks?: any[]
  equipment?: any[]
  all_items?: any[]
  // Для kanban
  columns?: Array<{
    status: string
    title: string
    tasks_count: number
    tasks: any[]
  }>
  // Общие поля
  events?: Array<{
    id: string
    name?: string
    title?: string
    start_date?: string
    date_start?: string
    end_date?: string
    date_end?: string
  }>
  start_date?: string
  end_date?: string
  first_day?: string
  last_day?: string
  month?: number
  year?: number
  detail_level?: string
  task_type_filter?: string
  equipment_included?: boolean
}

export const calendarApi = {
  getCalendar: async (params?: {
    view?: CalendarView
    start_date?: string
    end_date?: string
    task_type?: string
    detail_level?: DetailLevel
    include_equipment?: boolean
  }): Promise<CalendarResponse> => {
    const response = await api.get<CalendarResponse>('/calendar', { params })
    return response.data
  },

  getCalendarByRole: async (
    role: CalendarRole,
    params?: {
      view?: CalendarView
      start_date?: string
      end_date?: string
      detail_level?: DetailLevel
      include_equipment?: boolean
    }
  ): Promise<CalendarResponse> => {
    const response = await api.get<CalendarResponse>(`/calendar/by-role/${role}`, { params })
    return response.data
  },

  syncToSheets: async (params?: {
    month?: number
    year?: number
    role?: 'smm' | 'design' | 'channel' | 'prfr' | 'all'
  }): Promise<{ message: string; note?: string }> => {
    const response = await api.post('/calendar/sync/sheets', null, { params })
    return response.data
  },
}
