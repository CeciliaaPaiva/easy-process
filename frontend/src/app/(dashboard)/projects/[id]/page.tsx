'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ChevronLeft, Plus, FileText } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import type { Process, Project } from '@/types'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { StatusBadge } from '@/components/ui/status-badge'
import { AudioUploader } from '@/components/upload/AudioUploader'

function ProcessCard({ process, onClick }: { process: Process; onClick: () => void }) {
  return (
    <Card onClick={onClick} className="flex items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <FileText size={18} className="shrink-0 text-gray-400" />
        <div className="min-w-0">
          <p className="truncate font-medium text-gray-900">{process.name}</p>
          <p className="text-xs text-gray-400">
            {new Date(process.created_at).toLocaleDateString('pt-BR')}
          </p>
        </div>
      </div>
      <StatusBadge status={process.status} />
    </Card>
  )
}

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [project, setProject] = useState<Project | null>(null)
  const [processes, setProcesses] = useState<Process[]>([])
  const [loading, setLoading] = useState(true)
  const [showUpload, setShowUpload] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.projects.get(id), api.processes.list(id)])
      .then(([proj, procs]) => {
        setProject(proj)
        setProcesses(procs)
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : 'Erro ao carregar dados'))
      .finally(() => setLoading(false))
  }, [id])

  const handleUploaded = (process: Process) => {
    setProcesses((prev) => [process, ...prev])
    setShowUpload(false)
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error || 'Projeto não encontrado'}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <button
          onClick={() => router.push('/projects')}
          className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ChevronLeft size={16} />
          Projetos
        </button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
            {project.description && (
              <p className="mt-1 text-sm text-gray-500">{project.description}</p>
            )}
          </div>
          <Button onClick={() => setShowUpload(true)}>
            <Plus size={16} className="mr-1" />
            Novo processo
          </Button>
        </div>
      </div>

      {processes.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-gray-200 py-16 text-center">
          <FileText size={40} className="text-gray-300" />
          <p className="text-gray-500">Nenhum processo neste projeto</p>
          <Button variant="ghost" onClick={() => setShowUpload(true)}>
            Fazer upload de áudio
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {processes.map((p) => (
            <ProcessCard
              key={p.id}
              process={p}
              onClick={() => router.push(`/projects/${id}/processes/${p.id}`)}
            />
          ))}
        </div>
      )}

      <Dialog
        open={showUpload}
        onClose={() => setShowUpload(false)}
        title="Novo processo"
        className="max-w-lg"
      >
        <AudioUploader projectId={id} onUploaded={handleUploaded} />
      </Dialog>
    </div>
  )
}
