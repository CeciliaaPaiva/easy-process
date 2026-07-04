'use client'

import { useEffect, useState } from 'react'
import { RefreshCw, AlertTriangle, SearchCheck } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useToast } from '@/components/ui/toast'

interface Finding {
  title: string
  description: string
  severity: string
  related_elements: string[]
}

interface BottleneckData {
  findings: Finding[]
  disclaimer: string
}

const SEVERITY_STYLES: Record<string, string> = {
  alta: 'bg-red-100 text-red-700',
  média: 'bg-yellow-100 text-yellow-700',
  baixa: 'bg-gray-100 text-gray-600',
}

export function BottleneckPanel({ processId }: { processId: string }) {
  const { toast } = useToast()
  const [data, setData] = useState<BottleneckData | null>(null)
  const [loading, setLoading] = useState(true)
  const [regenerating, setRegenerating] = useState(false)
  const [error, setError] = useState('')

  const load = async (regen = false) => {
    regen ? setRegenerating(true) : setLoading(true)
    setError('')
    try {
      const method = regen ? 'post' : 'get'
      const result = await api[method]<BottleneckData>(
        `/api/v1/processes/${processId}/bottlenecks`,
        undefined
      )
      setData(result)
      if (regen) toast('Análise atualizada', 'success')
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Erro ao analisar gargalos'
      setError(msg)
      if (regen) toast(msg, 'error')
    } finally {
      regen ? setRegenerating(false) : setLoading(false)
    }
  }

  useEffect(() => { load() }, [processId]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="flex h-full flex-col gap-3 p-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
        <Skeleton className="mt-4 h-20 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <SearchCheck size={32} className="text-gray-300" />
        <p className="text-sm text-gray-500">{error}</p>
        <Button variant="ghost" onClick={() => load()}>Tentar novamente</Button>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-4 text-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Gargalos</h3>
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

      <div className="flex items-start gap-2 rounded-lg bg-blue-50 p-3 text-xs text-blue-800">
        <AlertTriangle size={14} className="mt-0.5 shrink-0" />
        <p>{data.disclaimer}</p>
      </div>

      {data.findings.length === 0 ? (
        <p className="text-gray-500">Nenhum gargalo identificado neste processo.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {data.findings.map((f, i) => (
            <div key={i} className="rounded-lg border border-gray-100 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-900">{f.title}</span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    SEVERITY_STYLES[f.severity] ?? SEVERITY_STYLES.baixa
                  }`}
                >
                  {f.severity}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-600">{f.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
