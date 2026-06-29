'use client'

import { useEffect, useRef } from 'react'

interface Props {
  xml: string
  className?: string
}

export function BpmnViewer({ xml, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<unknown>(null)

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

      try {
        await viewer.importXML(xml)
        const canvas = viewer.get('canvas') as { zoom: (fit: string, center: boolean) => void }
        canvas.zoom('fit-viewport', true)
      } catch (e) {
        console.error('bpmn-js import error', e)
      }
    }

    init()

    return () => {
      mounted = false
      if (viewerRef.current) {
        ;(viewerRef.current as { destroy: () => void }).destroy()
        viewerRef.current = null
      }
    }
  }, [xml])

  return <div ref={containerRef} className={className ?? 'h-full w-full'} />
}
