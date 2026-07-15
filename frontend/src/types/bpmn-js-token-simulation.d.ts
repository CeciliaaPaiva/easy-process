// bpmn-js-token-simulation não publica tipos — apenas o necessário para o
// bundle `viewer` (usado por BpmnViewer.tsx para o modo Apresentação).
declare module 'bpmn-js-token-simulation/lib/viewer' {
  const TokenSimulationViewerModule: Record<string, unknown>
  export default TokenSimulationViewerModule
}
