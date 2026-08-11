'use client'

import { useEffect, useState } from 'react'
import { api, ApiError } from '@/lib/api'
import type { UsageSummary } from '@/types'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/toast'

const stageLabels: Record<string, string> = {
  transcription: 'Transcrição',
  bpmn_analysis: 'Análise',
  bpmn_modeling: 'Modelagem BPMN',
  bpmn_refinement: 'Refinamento (chat)',
}

const DAYS_OPTIONS = [7, 30, 90] as const

function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`
}

function formatTokens(n: number): string {
  return n.toLocaleString('pt-BR')
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR')
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-gray-900">{value}</p>
    </Card>
  )
}

export default function AdminUsagePage() {
  const { toast } = useToast()
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [days, setDays] = useState<number>(30)
  const [loading, setLoading] = useState(true)
  const [forbidden, setForbidden] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    api.auth
      .me()
      .then((user) => {
        if (cancelled) return
        if (!user.is_platform_admin) {
          setForbidden(true)
          setLoading(false)
          return
        }
        return api.admin.usage(days).then((data) => {
          if (!cancelled) setUsage(data)
        })
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 403) {
          setForbidden(true)
        } else {
          toast('Erro ao carregar dados de uso', 'error')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [days, toast])

  if (!loading && forbidden) {
    return (
      <Card>
        <p className="text-sm text-gray-600">
          Apenas administradores podem ver os dados de uso da plataforma.
        </p>
      </Card>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Uso de IA</h1>
          <p className="text-sm text-gray-500">
            Tokens e custo estimado do pipeline de IA (Gemini), no seu workspace
          </p>
        </div>
        <div className="flex gap-1">
          {DAYS_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                days === d
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loading || !usage ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <StatCard label="Chamadas ao Gemini" value={formatTokens(usage.total_calls)} />
            <StatCard label="Tokens totais" value={formatTokens(usage.total_tokens)} />
            <StatCard
              label="Custo estimado"
              value={formatCost(usage.total_estimated_cost_usd)}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Por etapa do pipeline</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="pb-2 font-medium">Etapa</th>
                    <th className="pb-2 font-medium">Chamadas</th>
                    <th className="pb-2 font-medium">Tokens (in/out/cache)</th>
                    <th className="pb-2 font-medium">Custo</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.by_stage.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-4 text-gray-400">
                        Nenhum uso registrado neste período
                      </td>
                    </tr>
                  )}
                  {usage.by_stage.map((row) => (
                    <tr key={row.stage} className="border-b border-gray-100 last:border-0">
                      <td className="py-2">
                        <Badge variant="info">{stageLabels[row.stage] ?? row.stage}</Badge>
                      </td>
                      <td className="py-2">{formatTokens(row.calls)}</td>
                      <td className="py-2 text-gray-600">
                        {formatTokens(row.prompt_tokens)} / {formatTokens(row.output_tokens)} /{' '}
                        {formatTokens(row.cached_tokens)}
                      </td>
                      <td className="py-2 font-medium">{formatCost(row.estimated_cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Por dia</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="pb-2 font-medium">Dia</th>
                    <th className="pb-2 font-medium">Chamadas</th>
                    <th className="pb-2 font-medium">Tokens totais</th>
                    <th className="pb-2 font-medium">Custo</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.by_day.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-4 text-gray-400">
                        Sem dados neste período
                      </td>
                    </tr>
                  )}
                  {usage.by_day.map((row) => (
                    <tr key={row.day} className="border-b border-gray-100 last:border-0">
                      <td className="py-2">{row.day}</td>
                      <td className="py-2">{formatTokens(row.calls)}</td>
                      <td className="py-2">{formatTokens(row.total_tokens)}</td>
                      <td className="py-2 font-medium">{formatCost(row.estimated_cost_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Chamadas recentes</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-500">
                    <th className="pb-2 font-medium">Quando</th>
                    <th className="pb-2 font-medium">Etapa</th>
                    <th className="pb-2 font-medium">Modelo</th>
                    <th className="pb-2 font-medium">Tentativa</th>
                    <th className="pb-2 font-medium">Tokens</th>
                    <th className="pb-2 font-medium">Custo</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.recent_logs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-4 text-gray-400">
                        Nenhuma chamada registrada ainda
                      </td>
                    </tr>
                  )}
                  {usage.recent_logs.map((log) => (
                    <tr key={log.id} className="border-b border-gray-100 last:border-0">
                      <td className="py-2 text-gray-500">{formatDateTime(log.created_at)}</td>
                      <td className="py-2">{stageLabels[log.stage] ?? log.stage}</td>
                      <td className="py-2 text-gray-500">{log.model}</td>
                      <td className="py-2">
                        {log.attempt > 1 ? (
                          <Badge variant="warning">{log.attempt}ª</Badge>
                        ) : (
                          '1ª'
                        )}
                      </td>
                      <td className="py-2">{formatTokens(log.total_tokens)}</td>
                      <td className="py-2 font-medium">
                        {formatCost(log.estimated_cost_usd)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
