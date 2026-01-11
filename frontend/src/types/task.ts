export type TaskType = 'smm' | 'design' | 'channel' | 'prfr'
export type TaskStatus = 'draft' | 'open' | 'assigned' | 'in_progress' | 'review' | 'completed' | 'cancelled'
export type TaskPriority = 'low' | 'medium' | 'high' | 'critical'

export interface Task {
  id: string
  title: string
  description?: string
  type: TaskType
  event_id?: string
  priority: TaskPriority
  status: TaskStatus
  due_date?: string
  created_by: string
  created_at: string
  updated_at: string
  stages?: TaskStage[]
  assignments?: TaskAssignment[]
  thumbnail_image_url?: string
  role_specific_requirements?: {
    smm?: string
    design?: string
    channel?: string
    prfr?: string
  }
  questions?: string[]
  example_project_ids?: string[]
  equipment_available?: boolean
}

export interface TaskStage {
  id: string
  task_id: string
  stage_name: string
  stage_order: number
  due_date?: string
  status: 'pending' | 'in_progress' | 'completed'
  status_color: 'green' | 'yellow' | 'red' | 'purple' | 'blue'
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface TaskAssignment {
  id: string
  task_id: string
  user_id: string
  role_in_task: string
  status: 'assigned' | 'in_progress' | 'completed' | 'cancelled'
  rating?: number
  feedback?: string
  assigned_at: string
  completed_at?: string
}

export interface TaskStageCreate {
  stage_name: string
  stage_order: number
  due_date?: string
  status_color?: 'green' | 'yellow' | 'red' | 'purple' | 'blue'
}

export interface TaskCreate {
  title: string
  description?: string
  type: TaskType
  event_id?: string
  priority?: TaskPriority
  due_date?: string
  stages?: TaskStageCreate[]
  equipment_available?: boolean
  thumbnail_image_url?: string
  role_specific_requirements?: {
    smm?: string
    design?: string
    channel?: string
    prfr?: string
  }
  questions?: string[]
  example_project_ids?: string[]
}

export interface TaskUpdate {
  title?: string
  description?: string
  priority?: TaskPriority
  status?: TaskStatus
  due_date?: string
}

export interface TasksResponse {
  items: Task[]
  total: number
  skip: number
  limit: number
}
