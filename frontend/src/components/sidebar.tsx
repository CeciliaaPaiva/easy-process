'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  BarChart3,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  LogOut,
  Settings,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { clearTokens } from '@/lib/auth'
import { api } from '@/lib/api'

const navItems = [
  { href: '/projects', label: 'Projetos', icon: FolderOpen },
  { href: '/settings', label: 'Configurações', icon: Settings },
]

const adminNavItems = [
  { href: '/admin/usage', label: 'Uso de IA', icon: BarChart3 },
]

const STORAGE_KEY = 'easy-process:sidebar-collapsed'

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const [collapsed, setCollapsed] = useState(() =>
    typeof window === 'undefined' ? false : localStorage.getItem(STORAGE_KEY) === 'true'
  )
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    api.auth
      .me()
      .then((user) => setIsAdmin(user.role === 'admin'))
      .catch(() => setIsAdmin(false))
  }, [])

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(STORAGE_KEY, String(next))
      return next
    })
  }

  function handleLogout() {
    clearTokens()
    router.push('/login')
  }

  return (
    <aside
      suppressHydrationWarning
      className={cn(
        'flex h-screen flex-col border-r border-gray-200 bg-white transition-all',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center justify-between border-b border-gray-200 px-3">
        {!collapsed && (
          <span className="truncate px-3 text-lg font-bold text-blue-600">Easy Process</span>
        )}
        <button
          onClick={toggleCollapsed}
          title={collapsed ? 'Expandir menu' : 'Recolher menu'}
          className="ml-auto rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {[...navItems, ...(isAdmin ? adminNavItems : [])].map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            title={collapsed ? label : undefined}
            className={cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              pathname.startsWith(href)
                ? 'bg-blue-50 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
            )}
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {!collapsed && <span>{label}</span>}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-gray-200 p-3">
        <button
          onClick={handleLogout}
          title={collapsed ? 'Sair' : undefined}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900"
        >
          <LogOut className="h-4 w-4" />
          {!collapsed && <span>Sair</span>}
        </button>
      </div>
    </aside>
  )
}
