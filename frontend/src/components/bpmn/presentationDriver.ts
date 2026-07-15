// Lógica pura de "quem disparar a cada tick" do modo Apresentação. Separada do
// BpmnViewer para ser testável sem precisar renderizar um diagrama bpmn-js de
// verdade — recebe apenas o formato de subscription que `simulator.findSubscriptions({})`
// devolve (bpmn-js-token-simulation).
//
// Gateway exclusive/parallel/inclusive já são resolvidos automaticamente pela
// própria lib ao ativar o modo de simulação (activeOutgoing default por gateway).
// O que falta é disparar os elementos "aguardando trigger" (equivalente a clicar
// no play pad de cada elemento) a cada tick, para o token andar sozinho.

export const EXCLUSIVE_GATEWAY = 'bpmn:ExclusiveGateway'

export interface DriverElement {
  id: string
  type: string
}

export interface DriverSubscription {
  element: DriverElement | null | undefined
  event: unknown
  scope: unknown
}

/**
 * Agrupa subscriptions pendentes por elemento e decide quais disparar neste tick.
 * Gateways exclusive com mais de uma subscription pendente no mesmo elemento
 * (ramos concorrentes) disparam só um por vez, alternando a cada tick — os
 * demais tipos (parallel, tasks, eventos) disparam todos de uma vez.
 */
export function pickTriggers(
  subs: DriverSubscription[],
  rotation: Map<string, number>
): DriverSubscription[] {
  const groups = new Map<string, DriverSubscription[]>()

  subs.forEach((sub, index) => {
    const key = sub.element ? `el:${sub.element.id}` : `anon:${index}`
    const list = groups.get(key) ?? []
    list.push(sub)
    groups.set(key, list)
  })

  const picked: DriverSubscription[] = []

  groups.forEach((group, key) => {
    const type = group[0].element?.type
    if (group.length > 1 && type === EXCLUSIVE_GATEWAY) {
      const idx = (rotation.get(key) ?? 0) % group.length
      rotation.set(key, idx + 1)
      picked.push(group[idx])
    } else {
      picked.push(...group)
    }
  })

  return picked
}
