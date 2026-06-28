export interface User {
  id: string
  name: string
  email: string
  role: 'admin' | 'analyst' | 'viewer'
  tenant_id: string
  created_at: string
}

export interface Tenant {
  id: string
  name: string
  slug: string
  plan: 'free' | 'pro' | 'enterprise'
  created_at: string
}

export interface Project {
  id: string
  tenant_id: string
  name: string
  description?: string
  status: 'active' | 'archived'
  created_by: string
  created_at: string
  updated_at: string
}

export type ProcessStatus = 'pending' | 'transcribing' | 'generating' | 'ready' | 'error'

export interface Actor {
  name: string
  role?: string
}

export interface Task {
  name: string
  responsible?: string
  description?: string
}

export interface Process {
  id: string
  project_id: string
  tenant_id: string
  name: string
  audio_path?: string
  transcription?: string
  bpmn_xml?: string
  summary?: string
  actors: Actor[]
  tasks: Task[]
  version: number
  status: ProcessStatus
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  process_id: string
  role: 'user' | 'assistant'
  content: string
  bpmn_version?: number
  created_at: string
}

export interface ProcessVersion {
  id: string
  process_id: string
  version: number
  bpmn_xml: string
  change_description?: string
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface AuthResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}
