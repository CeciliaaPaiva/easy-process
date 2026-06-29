'use client'

import { useEffect, useState } from 'react'
import { RefreshCw, FileText } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/toast'

interface DocData {
  description: string
  activities: Array<{ name: string; responsible?: string; description?: string; inputs?: string[]; outputs?: string[] }>
  business_rules: string[]
  decision_points: Array<{ name: string; criteria?: string; outcomes?: string[] }>
  exceptions: string[]
}

export function DocsPanel({ processId }: { processId: string }) {
  const { toast } = useToast()
  const [doc, setDoc] = useState<DocData | null>(null)
  const [loading, setLoading] = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const [error, setError] = useState('')

  const load = async (regen = false) => {
    regen ? setRegenerating(true) : setLoading(true)
    setError('')
    try {
      const method = regen ? 'post' : 'get'
      const data = await api[method]<DocData>(`/api/v1/processes/${processId}/docs`, undefined)
      setDoc(data)
      if (regen) toast('Documentação regenerada', 'success')
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Erro ao carregar documentação'
      setError(msg)
      if (regen) toast(msg, 'error')
    } finally {
      regen ? setRegenerating(false) : setLoading(false)
    }
  }

  useEffect(() => { load() }, [processId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="flex flex-col gap-3 p-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="mt-4 h-24 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 p-6 text-center">
        <FileText size={32} className="text-gray-300" />
        <p className="text-sm text-gray-500">{error}</p>
        <Button variant="ghost" onClick={() => load()}>Tentar novamente</Button>
      </div>
    )
  }

  if (!doc) return null

  return (
    <div className="flex flex-col gap-4 overflow-y-auto p-4 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Documentação</h3>
        <Button
          variant="ghost"
          className="gap-1 text-xs"
          loading={regenerating}
          onClick={() => load(true)}
        >
          <RefreshCw size={12} />
          Regenerar
        </Button>
      </div>

      <section>
        <h4 className="mb-1 font-medium text-gray-700">Descrição geral</h4>
        <p className="text-gray-600 leading-relaxed">{doc.description}</p>
      </section>

      {doc.activities.length > 0 && (
        <section>
          <h4 className="mb-2 font-medium text-gray-700">Atividades</h4>
          <div className="flex flex-col gap-2">
            {doc.activities.map((a, i) => (
              <div key={i} className="rounded-lg border border-gray-100 p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-gray-900">{a.name}</span>
                  {a.responsible && (
                    <span className="text-xs text-gray-500">{a.responsible}</span>
                  )}
                </div>
                {a.description && <p className="mt-1 text-xs text-gray-600">{a.description}</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      {doc.business_rules.length > 0 && (
        <section>
          <h4 className="mb-2 font-medium text-gray-700">Regras de negócio</h4>
          <ul className="flex flex-col gap-1">
            {doc.business_rules.map((r, i) => (
              <li key={i} className="flex items-start gap-2 text-gray-600">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                {r}
              </li>
            ))}
          </ul>
        </section>
      )}

      {doc.decision_points.length > 0 && (
        <section>
          <h4 className="mb-2 font-medium text-gray-700">Pontos de decisão</h4>
          <div className="flex flex-col gap-2">
            {doc.decision_points.map((d, i) => (
              <div key={i} className="rounded-lg bg-yellow-50 p-3">
                <p className="font-medium text-yellow-800">{d.name}</p>
                {d.criteria && <p className="mt-0.5 text-xs text-yellow-700">{d.criteria}</p>}
              </div>
            ))}
          </div>
        </section>
      )}

      {doc.exceptions.length > 0 && (
        <section>
          <h4 className="mb-2 font-medium text-gray-700">Exceções</h4>
          <ul className="flex flex-col gap-1">
            {doc.exceptions.map((e, i) => (
              <li key={i} className="flex items-start gap-2 text-gray-600">
                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-red-400" />
                {e}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
