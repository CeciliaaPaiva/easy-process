export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-blue-600">Easy Process</h1>
        <p className="mt-1 text-sm text-gray-500">Plataforma BPMN com IA</p>
      </div>
      {children}
    </div>
  )
}
