import type {
  AuthResponse,
  ChatMessage,
  PaginatedResponse,
  Process,
  ProcessVersion,
  Project,
  User,
} from '@/types'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token =
    typeof window !== 'undefined' ? localStorage.getItem('access_token') : null

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Erro desconhecido' }))
    throw new ApiError(error.detail ?? `HTTP ${response.status}`, response.status)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),

  auth: {
    register: (body: { name: string; email: string; password: string; company: string }) =>
      request<AuthResponse>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    login: (email: string, password: string) =>
      request<AuthResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    me: () => request<User>('/api/v1/auth/me'),
  },

  projects: {
    list: (page = 1, perPage = 20) =>
      request<PaginatedResponse<Project>>(
        `/api/v1/projects?page=${page}&per_page=${perPage}`
      ),
    get: (id: string) => request<Project>(`/api/v1/projects/${id}`),
    create: (name: string, description?: string) =>
      request<Project>('/api/v1/projects', {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      }),
    update: (id: string, data: { name?: string; description?: string }) =>
      request<Project>(`/api/v1/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) => request<void>(`/api/v1/projects/${id}`, { method: 'DELETE' }),
  },

  processes: {
    list: (projectId: string) =>
      request<Process[]>(`/api/v1/projects/${projectId}/processes`),
    get: (id: string) => request<Process>(`/api/v1/processes/${id}`),
    status: (id: string) =>
      request<{ id: string; status: string; version: number }>(
        `/api/v1/processes/${id}/status`
      ),
    bpmn: (id: string) =>
      request<{ bpmn_xml: string; version: number }>(`/api/v1/processes/${id}/bpmn`),
    export: (id: string) => `${API_BASE_URL}/api/v1/processes/${id}/export`,
    upload: (
      projectId: string,
      name: string,
      audio: File,
      onProgress?: (pct: number) => void
    ) =>
      new Promise<Process>((resolve, reject) => {
        const token =
          typeof window !== 'undefined' ? localStorage.getItem('access_token') : null
        const form = new FormData()
        form.append('name', name)
        form.append('audio', audio)

        const xhr = new XMLHttpRequest()
        xhr.open('POST', `${API_BASE_URL}/api/v1/projects/${projectId}/processes`)
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
        }
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText) as Process)
          } else {
            const err = JSON.parse(xhr.responseText).detail ?? `HTTP ${xhr.status}`
            reject(new ApiError(err, xhr.status))
          }
        }
        xhr.onerror = () => reject(new ApiError('Erro de rede', 0))
        xhr.send(form)
      }),
  },

  versions: {
    list: (processId: string) =>
      request<ProcessVersion[]>(`/api/v1/processes/${processId}/versions`),
    get: (processId: string, version: number) =>
      request<ProcessVersion>(`/api/v1/processes/${processId}/versions/${version}`),
    restore: (processId: string, version: number) =>
      request<Process>(`/api/v1/processes/${processId}/versions/${version}/restore`, {
        method: 'POST',
      }),
  },

  chat: {
    history: (processId: string) =>
      request<ChatMessage[]>(`/api/v1/processes/${processId}/chat`),
    send: (processId: string, message: string) =>
      request<{
        bpmn_xml: string
        change_description: string
        version: number
        user_message: ChatMessage
        assistant_message: ChatMessage
      }>(`/api/v1/processes/${processId}/chat`, {
        method: 'POST',
        body: JSON.stringify({ message }),
      }),
  },
}
