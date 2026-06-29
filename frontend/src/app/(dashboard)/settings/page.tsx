'use client'

import { useEffect, useState } from 'react'
import { UserPlus, Trash2, Edit2, Check, X } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { User } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/toast'

const roleLabels: Record<string, string> = { admin: 'Admin', analyst: 'Analista', viewer: 'Leitor' }
const roleVariants: Record<string, 'default' | 'info' | 'warning'> = {
  admin: 'warning',
  analyst: 'info',
  viewer: 'default',
}

function InviteDialog({
  open,
  onClose,
  onInvited,
}: {
  open: boolean
  onClose: () => void
  onInvited: (u: User) => void
}) {
  const { toast } = useToast()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'admin' | 'analyst' | 'viewer'>('analyst')
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const user = await api.post<User>('/api/v1/tenants/invite', { email, name, role })
      toast('Membro convidado com sucesso', 'success')
      onInvited(user)
      setName(''); setEmail(''); setRole('analyst')
      onClose()
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Erro ao convidar', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Convidar membro">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
        <Input label="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-gray-700">Papel</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as 'admin' | 'analyst' | 'viewer')}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value="analyst">Analista</option>
            <option value="viewer">Leitor</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>Cancelar</Button>
          <Button type="submit" loading={loading} disabled={!name || !email}>Convidar</Button>
        </div>
      </form>
    </Dialog>
  )
}

function MemberRow({ member, currentUserId, onRoleChange, onRemove }: {
  member: User
  currentUserId: string
  onRoleChange: (id: string, role: string) => void
  onRemove: (id: string) => void
}) {
  const { toast } = useToast()
  const [editing, setEditing] = useState(false)
  const [newRole, setNewRole] = useState(member.role)
  const [loading, setLoading] = useState(false)
  const isSelf = member.id === currentUserId

  const saveRole = async () => {
    setLoading(true)
    try {
      await api.put(`/api/v1/tenants/members/${member.id}`, { role: newRole })
      onRoleChange(member.id, newRole)
      toast('Papel atualizado', 'success')
      setEditing(false)
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Erro ao atualizar', 'error')
    } finally {
      setLoading(false)
    }
  }

  const remove = async () => {
    if (!confirm(`Remover ${member.name} do tenant?`)) return
    setLoading(true)
    try {
      await api.delete(`/api/v1/tenants/members/${member.id}`)
      onRemove(member.id)
      toast('Membro removido', 'success')
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'Erro ao remover', 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-gray-100 p-4">
      <div className="min-w-0">
        <p className="font-medium text-gray-900">{member.name} {isSelf && <span className="text-xs text-gray-400">(você)</span>}</p>
        <p className="text-sm text-gray-500">{member.email}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {editing && !isSelf ? (
          <>
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value as 'admin' | 'analyst' | 'viewer')}
              className="rounded border border-gray-300 px-2 py-1 text-xs"
            >
              <option value="analyst">Analista</option>
              <option value="viewer">Leitor</option>
              <option value="admin">Admin</option>
            </select>
            <button onClick={saveRole} disabled={loading} className="text-green-600 hover:text-green-800">
              <Check size={15} />
            </button>
            <button onClick={() => setEditing(false)} className="text-gray-400 hover:text-gray-600">
              <X size={15} />
            </button>
          </>
        ) : (
          <>
            <Badge variant={roleVariants[member.role] ?? 'default'}>{roleLabels[member.role] ?? member.role}</Badge>
            {!isSelf && (
              <>
                <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-blue-600">
                  <Edit2 size={14} />
                </button>
                <button onClick={remove} disabled={loading} className="text-gray-400 hover:text-red-600">
                  <Trash2 size={14} />
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { toast } = useToast()
  const [me, setMe] = useState<User | null>(null)
  const [members, setMembers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [showInvite, setShowInvite] = useState(false)

  useEffect(() => {
    Promise.all([api.auth.me(), api.get<User[]>('/api/v1/tenants/members')])
      .then(([user, list]) => { setMe(user); setMembers(list) })
      .catch(() => toast('Erro ao carregar configurações', 'error'))
      .finally(() => setLoading(false))
  }, [toast])

  const handleRoleChange = (id: string, role: string) =>
    setMembers((prev) =>
      prev.map((m) => (m.id === id ? { ...m, role: role as User['role'] } : m))
    )

  const handleRemove = (id: string) =>
    setMembers((prev) => prev.filter((m) => m.id !== id))

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Configurações</h1>
        <p className="text-sm text-gray-500">Gerencie membros e permissões do seu workspace</p>
      </div>

      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">Membros</h2>
          {me?.role === 'admin' && (
            <Button onClick={() => setShowInvite(true)} className="gap-1 text-sm">
              <UserPlus size={14} />
              Convidar
            </Button>
          )}
        </div>
        <div className="flex flex-col gap-2">
          {loading
            ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)
            : members.map((m) => (
                <MemberRow
                  key={m.id}
                  member={m}
                  currentUserId={me?.id ?? ''}
                  onRoleChange={handleRoleChange}
                  onRemove={handleRemove}
                />
              ))
          }
        </div>
      </Card>

      <InviteDialog
        open={showInvite}
        onClose={() => setShowInvite(false)}
        onInvited={(u) => setMembers((prev) => [...prev, u])}
      />
    </div>
  )
}
