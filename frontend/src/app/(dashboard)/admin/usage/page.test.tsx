import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import AdminUsagePage from './page'
import { api } from '@/lib/api'

vi.mock('@/lib/api', () => ({
  api: {
    auth: { me: vi.fn() },
    admin: { usage: vi.fn() },
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.status = status
    }
  },
}))

const mockedApi = vi.mocked(api, true)

describe('AdminUsagePage', () => {
  it('shows a permission message for non-admin users', async () => {
    mockedApi.auth.me.mockResolvedValue({
      id: '1',
      name: 'Analista',
      email: 'a@a.com',
      role: 'analyst',
      tenant_id: 't1',
      is_platform_admin: false,
      created_at: '2026-01-01',
    })

    render(<AdminUsagePage />)

    expect(await screen.findByText(/apenas administradores/i)).toBeInTheDocument()
    expect(mockedApi.admin.usage).not.toHaveBeenCalled()
  })

  it('shows a permission message for tenant admins without platform access', async () => {
    // role="admin" só dá acesso a gerenciar o próprio tenant — o painel de
    // uso agregado da plataforma exige is_platform_admin (S11-01).
    mockedApi.auth.me.mockResolvedValue({
      id: '1',
      name: 'Admin do tenant',
      email: 'tenant-admin@a.com',
      role: 'admin',
      tenant_id: 't1',
      is_platform_admin: false,
      created_at: '2026-01-01',
    })

    render(<AdminUsagePage />)

    expect(await screen.findByText(/apenas administradores/i)).toBeInTheDocument()
    expect(mockedApi.admin.usage).not.toHaveBeenCalled()
  })

  it('renders totals and stage breakdown for platform admins', async () => {
    mockedApi.auth.me.mockResolvedValue({
      id: '1',
      name: 'Admin',
      email: 'admin@a.com',
      role: 'admin',
      tenant_id: 't1',
      is_platform_admin: true,
      created_at: '2026-01-01',
    })
    mockedApi.admin.usage.mockResolvedValue({
      total_calls: 3,
      total_prompt_tokens: 1000,
      total_output_tokens: 400,
      total_cached_tokens: 0,
      total_tokens: 1400,
      total_estimated_cost_usd: 0.0012,
      by_stage: [
        {
          stage: 'bpmn_generation',
          calls: 3,
          prompt_tokens: 1000,
          output_tokens: 400,
          cached_tokens: 0,
          total_tokens: 1400,
          estimated_cost_usd: 0.0012,
        },
      ],
      by_day: [],
      recent_logs: [],
    })

    render(<AdminUsagePage />)

    await waitFor(() => expect(screen.getByText('1.400')).toBeInTheDocument())
    expect(screen.getByText('Geração BPMN')).toBeInTheDocument()
    expect(screen.getAllByText('$0.0012').length).toBeGreaterThan(0)
  })
})
