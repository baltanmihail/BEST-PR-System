export enum UserRole {
  NOVICE = 'novice',
  PARTICIPANT = 'participant',
  ACTIVE_PARTICIPANT = 'active_participant',
  COORDINATOR_SMM = 'coordinator_smm',
  COORDINATOR_DESIGN = 'coordinator_design',
  COORDINATOR_CHANNEL = 'coordinator_channel',
  COORDINATOR_PRFR = 'coordinator_prfr',
  VP4PR = 'vp4pr'
}

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
