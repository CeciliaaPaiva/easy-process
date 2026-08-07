const PNG_EXPORT_SCALE = 2

function getSvgDimensions(svgMarkup: string): { width: number; height: number } {
  const doc = new DOMParser().parseFromString(svgMarkup, 'image/svg+xml')
  const svg = doc.documentElement
  const viewBox = svg.getAttribute('viewBox')
  if (viewBox) {
    const parts = viewBox.split(/\s+/).map(Number)
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { width: parts[2], height: parts[3] }
    }
  }
  const width = parseFloat(svg.getAttribute('width') ?? '') || 1000
  const height = parseFloat(svg.getAttribute('height') ?? '') || 700
  return { width, height }
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

async function svgToPngBlob(
  svgMarkup: string,
  scale = PNG_EXPORT_SCALE
): Promise<{ blob: Blob; width: number; height: number }> {
  const { width, height } = getSvgDimensions(svgMarkup)
  const svgBlob = new Blob([svgMarkup], { type: 'image/svg+xml;charset=utf-8' })
  const url = URL.createObjectURL(svgBlob)
  try {
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image()
      image.onload = () => resolve(image)
      image.onerror = () => reject(new Error('Falha ao carregar o SVG do diagrama'))
      image.src = url
    })

    const canvas = document.createElement('canvas')
    canvas.width = Math.round(width * scale)
    canvas.height = Math.round(height * scale)
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D indisponível neste navegador')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
    if (!blob) throw new Error('Falha ao gerar PNG a partir do diagrama')
    return { blob, width, height }
  } finally {
    URL.revokeObjectURL(url)
  }
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export async function exportBpmnAsPng(svgMarkup: string, filename: string): Promise<void> {
  const { blob } = await svgToPngBlob(svgMarkup)
  downloadBlob(blob, filename)
}

export async function exportBpmnAsPdf(svgMarkup: string, filename: string): Promise<void> {
  const { jsPDF } = await import('jspdf')
  const { blob, width, height } = await svgToPngBlob(svgMarkup)
  const dataUrl = await blobToDataUrl(blob)

  // Página do PDF dimensionada exatamente ao tamanho do diagrama (unidade
  // 'pt' == 1px do SVG) em vez de A4 fixo — evita diagramas grandes/largos
  // ficarem ilegíveis por cortarem ou espremerem numa proporção de página
  // que não é a deles.
  const doc = new jsPDF({
    orientation: width >= height ? 'landscape' : 'portrait',
    unit: 'pt',
    format: [width, height],
  })
  doc.addImage(dataUrl, 'PNG', 0, 0, width, height)
  downloadBlob(doc.output('blob'), filename)
}
