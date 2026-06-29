'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search, FolderOpen } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { Project } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'

function ProjectCard({ project, onClick }: { project: Project; onClick: () => void }) {
  return (
    <Card onClick={onClick} className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <FolderOpen size={18} className="shrink-0 text-blue-500" />
        <span className="font-semibold text-gray-900 line-clamp-1">{project.name}</span>
      </div>
      {project.description && (
        <p className="text-sm text-gray-500 line-clamp-2">{project.description}</p>
      )}
      <p className="text-xs text-gray-400">
        Criado em {new Date(project.created_at).toLocaleDateString('pt-BR')}
      </p>
    </Card>
  )
}

function CreateProjectDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  onCreated: (p: Project) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    setError('')
    try {
      const project = await api.projects.create(name.trim(), description.trim() || undefined)
      onCreated(project)
      setName('')
      setDescription('')
      onClose()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao criar projeto')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} title="Novo projeto">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Nome"
          placeholder="Ex: Processo de onboarding"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          autoFocus
        />
        <Input
          label="Descrição (opcional)"
          placeholder="Descreva o objetivo do projeto"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>
            Cancelar
          </Button>
          <Button type="submit" loading={loading} disabled={!name.trim()}>
            Criar projeto
          </Button>
        </div>
      </form>
    </Dialog>
  )
}

export default function ProjectsPage() {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [filtered, setFiltered] = useState<Project[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.projects
      .list()
      .then((res) => setProjects(res.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Erro ao carregar projetos'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    const q = search.toLowerCase()
    setFiltered(
      q
        ? projects.filter(
            (p) =>
              p.name.toLowerCase().includes(q) ||
              p.description?.toLowerCase().includes(q)
          )
        : projects
    )
  }, [search, projects])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projetos</h1>
          <p className="text-sm text-gray-500">Organize seus processos por projeto</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus size={16} className="mr-1" />
          Novo projeto
        </Button>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Buscar projetos..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-4 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <FolderOpen size={40} className="text-gray-300" />
          <p className="text-gray-500">
            {search ? 'Nenhum projeto encontrado' : 'Nenhum projeto ainda'}
          </p>
          {!search && (
            <Button variant="ghost" onClick={() => setShowCreate(true)}>
              Criar primeiro projeto
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              onClick={() => router.push(`/projects/${p.id}`)}
            />
          ))}
        </div>
      )}

      <CreateProjectDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={(p) => setProjects((prev) => [p, ...prev])}
      />
    </div>
  )
}
