export enum UserRole {
  NOVICE = 'novice',
  PARTICIPANT = 'participant',
  ACTIVE_PARTICIPANT = 'active_participant',
  COORDINATOR_SMM = 'coordinator_smm',
  COORDINATOR_DESIGN = 'coordinator_design',
  COORDINATOR_CHANNEL = 'coordinator_channel',
  COORDINATOR_PRFR = 'coordinator_prfr',
  VP4PR = 'vp4pr',
  ADMIN = 'admin'
}

export function isPrivileged(role: UserRole | string): boolean {
  return role === UserRole.VP4PR || role === UserRole.ADMIN || role === 'vp4pr' || role === 'admin'
}

export function isCoordinatorOrAbove(role: UserRole | string): boolean {
  return isPrivileged(role) || [
    UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
    UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR,
    'coordinator_smm', 'coordinator_design', 'coordinator_channel', 'coordinator_prfr'
  ].includes(role as any)
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
  last_activity_at?: string
  created_at: string
  updated_at: string
  is_active: boolean
  avatar_url?: string
  bio?: string
  contacts?: {
    email?: string
    phone?: string
    telegram?: string
    vk?: string
    instagram?: string
  }
  skills?: string[]
  portfolio?: Array<{
    title: string
    description?: string
    url: string
    type: 'photo' | 'video' | 'link'
    gallery_item_id?: string
  }>
}
