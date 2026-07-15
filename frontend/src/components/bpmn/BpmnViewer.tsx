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
// Ticks seguidos sem nenhuma subscription pendente antes de considerar
// reiniciar o loop — é só um debounce contra uma folga isolada entre passos;
// quem decide de fato que a volta terminou é reachedEndRef (ver abaixo).
const IDLE_TICKS_TO_LOOP = 2
// Cada travessia de sequenceFlow é animada (tempo real, pautado por
// animation.setAnimationSpeed), não instantânea — então "0 subscriptions
// pendentes" não significa "chegou ao fim", só "nada esperando input" nesse
// instante; o token pode estar no meio de uma transição animada. Rede de
// segurança: se ficar ocioso por muito tempo sem NUNCA alcançar um end event
// (ex.: diagrama com um caminho sem saída), força o reinício mesmo assim, em
// vez de travar o modo Apresentação para sempre.
const SAFETY_IDLE_TICKS_TO_FORCE_LOOP = 20

interface BpmnCanvas {
  zoom: (fit: string, center: boolean) => void
  addMarker: (elementId: string, cls: string) => void
  removeMarker: (elementId: string, cls: string) => void
}

interface SimulatorElement {
  id: string
  type: string
}

interface Simulator {
  findSubscriptions: (filter: Record<string, never>) => DriverSubscription[]
  trigger: (context: { event: unknown; scope: unknown }) => unknown
  reset: () => void
  on: (event: string, callback: (payload: { element: SimulatorElement }) => void) => void
  off: (event: string, callback: (payload: { element: SimulatorElement }) => void) => void
}

interface ToggleMode {
  toggleMode: (active?: boolean) => void
}

interface AnimationService {
  setAnimationSpeed: (speed: number) => void
}

interface ExclusiveGatewaySettings {
  setSequenceFlow: (gateway: SimulatorElement) => void
}

interface ElementRegistry {
  get: (id: string) => SimulatorElement | undefined
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
const END_EVENT_TYPE = 'bpmn:EndEvent'

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
  // Ids de exclusive gateway visitados (token passou por eles) desde o último
  // tick — populado pelo listener `elementChanged` da lib, sincronamente,
  // durante os `trigger()` do tick anterior. Girar o ramo aqui em cada visita
  // real (em vez de por tempo/loop completo) é o que faz processos com loop
  // de retrabalho — o gateway é revisitado várias vezes e o processo nunca
  // fica ocioso — também alternarem de ramo, ao invés de ficar preso
  // reciclando sempre o primeiro ramo.
  const visitedGatewaysRef = useRef<Set<string>>(new Set())
  // true assim que um end event é alcançado na volta atual — é o sinal real
  // de "terminou", em vez de inferir pelo número de subscriptions pendentes.
  const reachedEndRef = useRef(false)

  const tick = useCallback(() => {
    const services = viewerRef.current
    if (!services) return
    const simulator = services.get('simulator') as Simulator

    if (visitedGatewaysRef.current.size > 0) {
      const elementRegistry = services.get('elementRegistry') as ElementRegistry
      const exclusiveGatewaySettings = services.get(
        'exclusiveGatewaySettings'
      ) as ExclusiveGatewaySettings
      visitedGatewaysRef.current.forEach((id) => {
        const gateway = elementRegistry.get(id)
        if (gateway) exclusiveGatewaySettings.setSequenceFlow(gateway)
      })
      visitedGatewaysRef.current.clear()
    }

    if (awaitingKickRef.current) {
      // dispara os start events uma única vez para iniciar a instância
      reachedEndRef.current = false
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
      const readyToLoop =
        idleTicksRef.current >= IDLE_TICKS_TO_LOOP &&
        (reachedEndRef.current || idleTicksRef.current >= SAFETY_IDLE_TICKS_TO_FORCE_LOOP)
      if (readyToLoop) {
        idleTicksRef.current = 0
        rotationRef.current.clear()
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
    visitedGatewaysRef.current.clear()
    idleTicksRef.current = 0
    awaitingKickRef.current = true
    reachedEndRef.current = false

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
      visitedGatewaysRef.current.clear()
      reachedEndRef.current = false
      ;(viewer.get('simulator') as Simulator).on('elementChanged', ({ element }) => {
        if (element.type === EXCLUSIVE_GATEWAY_TYPE) {
          visitedGatewaysRef.current.add(element.id)
        } else if (element.type === END_EVENT_TYPE) {
          reachedEndRef.current = true
        }
      })

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
