import { describe, expect, it } from 'vitest'
import { pickTriggers, type DriverSubscription } from './presentationDriver'

function sub(id: string, type: string, tag: string): DriverSubscription {
  return { element: { id, type }, event: tag, scope: {} }
}

describe('pickTriggers', () => {
  it('dispara todas as subscriptions de elementos não-gateway (ex.: parallel gateway forka tudo)', () => {
    const subs = [
      sub('Flow_1', 'bpmn:SequenceFlow', 'a'),
      sub('Flow_2', 'bpmn:SequenceFlow', 'b'),
      sub('Task_1', 'bpmn:Task', 'c'),
    ]
    const picked = pickTriggers(subs, new Map())
    expect(picked).toHaveLength(3)
  })

  it('exclusive gateway com ramos concorrentes dispara só um por tick', () => {
    const subs = [
      sub('Gw_1', 'bpmn:ExclusiveGateway', 'ramo-a'),
      sub('Gw_1', 'bpmn:ExclusiveGateway', 'ramo-b'),
    ]
    const rotation = new Map<string, number>()

    const first = pickTriggers(subs, rotation)
    expect(first).toHaveLength(1)
    expect(first[0].event).toBe('ramo-a')
  })

  it('alterna o ramo do exclusive gateway a cada chamada (cicla)', () => {
    const subs = [
      sub('Gw_1', 'bpmn:ExclusiveGateway', 'ramo-a'),
      sub('Gw_1', 'bpmn:ExclusiveGateway', 'ramo-b'),
    ]
    const rotation = new Map<string, number>()

    const first = pickTriggers(subs, rotation)
    const second = pickTriggers(subs, rotation)
    const third = pickTriggers(subs, rotation)

    expect([first[0].event, second[0].event, third[0].event]).toEqual([
      'ramo-a',
      'ramo-b',
      'ramo-a',
    ])
  })

  it('exclusive gateway com um único ramo pendente dispara normalmente', () => {
    const subs = [sub('Gw_1', 'bpmn:ExclusiveGateway', 'unico')]
    const picked = pickTriggers(subs, new Map())
    expect(picked).toHaveLength(1)
  })

  it('subscriptions sem elemento (ex.: eventos de processo) não são agrupadas entre si', () => {
    const subs: DriverSubscription[] = [
      { element: null, event: 'a', scope: {} },
      { element: null, event: 'b', scope: {} },
    ]
    const picked = pickTriggers(subs, new Map())
    expect(picked).toHaveLength(2)
  })
})
