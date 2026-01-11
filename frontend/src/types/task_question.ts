export interface TaskQuestion {
  id: string
  task_id: string
  asked_by_id: string
  answered_by_id?: string
  question: string
  answer?: string
  is_answered: boolean
  asked_at: string
  answered_at?: string
  asked_by_name?: string
  answered_by_name?: string
}
