'use client'

import { useCallback, useEffect, useRef } from 'react'

import 'bpmn-js/dist/assets/diagram-js.css'
import 'bpmn-js/dist/assets/bpmn-js.css'
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css'
import 'bpmn-js-token-simulation/assets/css/bpmn-js-token-simulation.css'

import { pickTriggers, type DriverSubscription } from './presentationDriver'

const HIGHLIGHT_MARKER = 'bpmn-suggestion-highlight'

// Intervalo base (ms) entre disparos automáticos do modo Apresentação, escalado
// pela velocidade escolhida na BpmnToolbar (0.5x/1x/2x).
const BASE_TICK_MS = 900
// Ticks seguidos sem nenhuma subscription pendente = animação chegou ao fim
// (todos os end events alcançados); reinicia para virar um loop contínuo.
const IDLE_TICKS_TO_LOOP = 2

interface BpmnCanvas {
  zoom: (fit: string, center: boolean) => void
  addMarker: (elementId: string, cls: string) => void
  removeMarker: (elementId: string, cls: string) => void
}

interface Simulator {
  findSubscriptions: (filter: Record<string, never>) => DriverSubscription[]
  trigger: (context: { event: unknown; scope: unknown }) => unknown
  reset: () => void
}

interface ToggleMode {
  toggleMode: (active?: boolean) => void
}

interface AnimationService {
  setAnimationSpeed: (speed: number) => void
}

interface ExclusiveGatewaySettings {
  setSequenceFlow: (gateway: { type: string }) => void
}

interface ElementRegistry {
  filter: (fn: (el: { type: string }) => boolean) => { type: string }[]
}

interface BpmnServices {
  get: (name: string) => unknown
}

const EXCLUSIVE_GATEWAY_TYPE = 'bpmn:ExclusiveGateway'
// A subscription do start event nunca é removida (a lib permite disparar uma
// nova instância a qualquer momento) — se o driver a disparasse a cada tick,
// criaria uma instância nova do processo em paralelo a cada vez. Só é
// disparada explicitamente no "kick" (início/reinício de loop); depois disso
// é ignorada no dreno de subscriptions pendentes.
const START_EVENT_TYPE = 'bpmn:StartEvent'

// A lib resolve o ramo de cada exclusive gateway só uma vez, ao entrar em modo
// de simulação (primeiro outgoing por padrão) — sem isso, o loop contínuo do
// modo Apresentação sempre repetiria o mesmo ramo. Giramos manualmente para o
// próximo outgoing a cada reinício do loop.
function rotateExclusiveGateways(services: BpmnServices) {
  const elementRegistry = services.get('elementRegistry') as ElementRegistry
  const exclusiveGatewaySettings = services.get(
    'exclusiveGatewaySettings'
  ) as ExclusiveGatewaySettings

  for (const gateway of elementRegistry.filter((el) => el.type === EXCLUSIVE_GATEWAY_TYPE)) {
    exclusiveGatewaySettings.setSequenceFlow(gateway)
  }
}

export type PresentationStatus = 'stopped' | 'playing' | 'paused'

export interface PresentationState {
  status: PresentationStatus
  speed: number
}

interface Props {
  xml: string
  className?: string
  highlightIds?: string[]
  presentation?: PresentationState
}

export function BpmnViewer({ xml, className, highlightIds, presentation }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<BpmnServices | null>(null)
  const highlightedRef = useRef<string[]>([])
  const tickIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const rotationRef = useRef<Map<string, number>>(new Map())
  const idleTicksRef = useRef(0)
  const presentationActiveRef = useRef(false)
  const awaitingKickRef = useRef(true)

  const tick = useCallback(() => {
    const services = viewerRef.current
    if (!services) return
    const simulator = services.get('simulator') as Simulator

    if (awaitingKickRef.current) {
      // dispara os start events uma única vez para iniciar a instância
      for (const sub of simulator.findSubscriptions({})) {
        simulator.trigger({ event: sub.event, scope: sub.scope })
      }
      awaitingKickRef.current = false
      idleTicksRef.current = 0
      return
    }

    const subs = simulator
      .findSubscriptions({})
      .filter((sub) => sub.element?.type !== START_EVENT_TYPE)

    if (subs.length === 0) {
      idleTicksRef.current += 1
      if (idleTicksRef.current >= IDLE_TICKS_TO_LOOP) {
        idleTicksRef.current = 0
        rotationRef.current.clear()
        rotateExclusiveGateways(services)
        simulator.reset()
        awaitingKickRef.current = true
      }
      return
    }

    idleTicksRef.current = 0
    for (const sub of pickTriggers(subs, rotationRef.current)) {
      simulator.trigger({ event: sub.event, scope: sub.scope })
    }
  }, [])

  const pausePresentationTick = useCallback(() => {
    if (tickIntervalRef.current) {
      clearInterval(tickIntervalRef.current)
      tickIntervalRef.current = null
    }
  }, [])

  const stopPresentation = useCallback(() => {
    pausePresentationTick()
    rotationRef.current.clear()
    idleTicksRef.current = 0
    awaitingKickRef.current = true

    if (presentationActiveRef.current && viewerRef.current) {
      const services = viewerRef.current
      ;(services.get('simulator') as Simulator).reset()
      ;(services.get('toggleMode') as ToggleMode).toggleMode(false)
    }
    presentationActiveRef.current = false
  }, [pausePresentationTick])

  const startPresentation = useCallback(
    (speed: number) => {
      const services = viewerRef.current
      if (!services) return

      const isFreshStart = !presentationActiveRef.current

      // idempotente: se já ativo, não reseta o progresso da simulação em curso
      ;(services.get('toggleMode') as ToggleMode).toggleMode(true)
      ;(services.get('animation') as AnimationService).setAnimationSpeed(speed)
      presentationActiveRef.current = true
      // só dispara o "kick" (start events) num início novo — retomar de pause
      // não deve criar outra instância do processo
      if (isFreshStart) {
        awaitingKickRef.current = true
        idleTicksRef.current = 0
      }

      pausePresentationTick()
      tickIntervalRef.current = setInterval(tick, Math.max(150, BASE_TICK_MS / speed))
    },
    [pausePresentationTick, tick]
  )

  useEffect(() => {
    let mounted = true

    async function init() {
      // Dynamic import because bpmn-js / token-simulation are browser-only
      const [{ default: BpmnJS }, { default: TokenSimulationModule }] = await Promise.all([
        import('bpmn-js'),
        import('bpmn-js-token-simulation/lib/viewer'),
      ])
      if (!mounted || !containerRef.current) return

      if (viewerRef.current) {
        stopPresentation()
        ;(viewerRef.current as unknown as { destroy: () => void }).destroy()
      }

      const viewer = new BpmnJS({
        container: containerRef.current,
        additionalModules: [TokenSimulationModule],
      })
      viewerRef.current = viewer as unknown as BpmnServices
      highlightedRef.current = []

      try {
        await viewer.importXML(xml)
        const canvas = viewer.get('canvas') as BpmnCanvas
        canvas.zoom('fit-viewport', true)
        applyHighlights(canvas, highlightIds ?? [])
      } catch (e) {
        console.error('bpmn-js import error', e)
      }
    }

    function applyHighlights(canvas: BpmnCanvas, ids: string[]) {
      for (const id of highlightedRef.current) {
        canvas.removeMarker(id, HIGHLIGHT_MARKER)
      }
      for (const id of ids) {
        try {
          canvas.addMarker(id, HIGHLIGHT_MARKER)
        } catch {
          // element not found in this diagram — ignore
        }
      }
      highlightedRef.current = ids
    }

    init()

    return () => {
      mounted = false
      stopPresentation()
      if (viewerRef.current) {
        ;(viewerRef.current as unknown as { destroy: () => void }).destroy()
        viewerRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [xml])

  useEffect(() => {
    const viewer = viewerRef.current as { get: (name: string) => unknown } | null
    if (!viewer) return
    const canvas = viewer.get('canvas') as BpmnCanvas
    for (const id of highlightedRef.current) {
      canvas.removeMarker(id, HIGHLIGHT_MARKER)
    }
    const ids = highlightIds ?? []
    for (const id of ids) {
      try {
        canvas.addMarker(id, HIGHLIGHT_MARKER)
      } catch {
        // element not found in this diagram — ignore
      }
    }
    highlightedRef.current = ids
  }, [highlightIds])

  useEffect(() => {
    if (!viewerRef.current) return
    if (presentation?.status === 'playing') {
      startPresentation(presentation.speed || 1)
    } else if (presentation?.status === 'paused') {
      pausePresentationTick()
    } else {
      stopPresentation()
    }
  }, [
    presentation?.status,
    presentation?.speed,
    startPresentation,
    pausePresentationTick,
    stopPresentation,
  ])

  return <div ref={containerRef} className={className ?? 'h-full w-full'} />
}
