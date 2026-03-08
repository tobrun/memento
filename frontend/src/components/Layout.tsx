import { Link, useRouterState } from '@tanstack/react-router'
import { BrainCircuit, Upload, Search, LayoutDashboard, Database } from 'lucide-react'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/ingest', label: 'Ingest', icon: Upload },
  { to: '/query', label: 'Query', icon: Search },
  { to: '/datasources', label: 'Datasources', icon: Database },
]

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const routerState = useRouterState()
  const currentPath = routerState.location.pathname

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside
        style={{
          width: '240px',
          minWidth: '240px',
          backgroundColor: '#0D1117',
          borderRight: '1px solid #21262D',
          display: 'flex',
          flexDirection: 'column',
          padding: '0',
          position: 'sticky',
          top: 0,
          height: '100vh',
        }}
      >
        {/* Logo/Brand */}
        <div
          style={{
            padding: '24px 20px',
            borderBottom: '1px solid #21262D',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <BrainCircuit size={28} style={{ color: '#7C3AED' }} />
          <span style={{ fontSize: '18px', fontWeight: 700, color: '#e6edf3' }}>Memento</span>
        </div>

        {/* Navigation */}
        <nav style={{ padding: '12px 8px', flex: 1 }}>
          {navItems.map(({ to, label, icon: Icon }) => {
            const isActive = currentPath === to || currentPath.startsWith(to + '/')
            return (
              <Link
                key={to}
                to={to}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  marginBottom: '2px',
                  textDecoration: 'none',
                  fontSize: '14px',
                  fontWeight: isActive ? 600 : 400,
                  color: isActive ? '#7C3AED' : '#8B949E',
                  backgroundColor: isActive ? 'rgba(124, 58, 237, 0.15)' : 'transparent',
                  transition: 'all 0.15s ease',
                }}
              >
                <Icon size={16} />
                {label}
              </Link>
            )
          })}
        </nav>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'auto', backgroundColor: '#0D1117' }}>
        {children}
      </main>
    </div>
  )
}
