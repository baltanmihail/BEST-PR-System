export type UserRole = 
  | 'novice'
  | 'participant'
  | 'active_participant'
  | 'coordinator_smm'
  | 'coordinator_design'
  | 'coordinator_channel'
  | 'coordinator_prfr'
  | 'vp4pr'

export interface User {
  id: string
  telegram_id: number
  username?: string
  telegram_username?: string // Альтернативное имя для username из Telegram
  email?: string // Email пользователя (если указан)
  full_name: string
  role: UserRole
  level: number
  points: number
  streak_days: number
  last_activity?: string
  created_at: string
  updated_at: string
  is_active: boolean
}
