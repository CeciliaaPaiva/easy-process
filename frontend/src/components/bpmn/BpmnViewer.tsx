'use client'

import { useEffect, useRef } from 'react'

import 'bpmn-js/dist/assets/diagram-js.css'
import 'bpmn-js/dist/assets/bpmn-js.css'
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn-embedded.css'

const HIGHLIGHT_MARKER = 'bpmn-suggestion-highlight'

interface BpmnCanvas {
  zoom: (fit: string, center: boolean) => void
  addMarker: (elementId: string, cls: string) => void
  removeMarker: (elementId: string, cls: string) => void
}

interface Props {
  xml: string
  className?: string
  highlightIds?: string[]
}

export function BpmnViewer({ xml, className, highlightIds }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<unknown>(null)
  const highlightedRef = useRef<string[]>([])

  useEffect(() => {
    let mounted = true

    async function init() {
      // Dynamic import because bpmn-js is browser-only
      const BpmnJS = (await import('bpmn-js')).default
      if (!mounted || !containerRef.current) return

      if (viewerRef.current) {
        ;(viewerRef.current as { destroy: () => void }).destroy()
      }

      const viewer = new BpmnJS({ container: containerRef.current })
      viewerRef.current = viewer
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
      if (viewerRef.current) {
        ;(viewerRef.current as { destroy: () => void }).destroy()
        viewerRef.current = null
      }
    }
  }, [xml]) // eslint-disable-line react-hooks/exhaustive-deps

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

  return <div ref={containerRef} className={className ?? 'h-full w-full'} />
}
