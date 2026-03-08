import { useState, useEffect, useCallback } from 'react'
import { Link } from '@tanstack/react-router'
import { fetchDatasources, fetchStatus, type Datasource, type StatusResponse } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { AlertTriangle, WifiOff, Database, Brain, Layers } from 'lucide-react'

interface DatasourceStats {
  datasource: Datasource
  status: StatusResponse | null
  error: string | null
}

export function DashboardPage() {
  const [statsMap, setStatsMap] = useState<DatasourceStats[]>([])
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [offline, setOffline] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const datasources = await fetchDatasources()
      setOffline(false)

      const results: DatasourceStats[] = await Promise.all(
        datasources.map(async (ds) => {
          try {
            const status = await fetchStatus(ds.name)
            return { datasource: ds, status, error: null }
          } catch (err) {
            return {
              datasource: ds,
              status: null,
              error: err instanceof Error ? err.message : 'Failed to fetch status',
            }
          }
        }),
      )

      setStatsMap(results)
      setLastUpdated(new Date())
    } catch {
      setOffline(true)
    }
  }, [])

  useEffect(() => {
    void fetchAll()
    const interval = setInterval(() => void fetchAll(), 10000)
    return () => clearInterval(interval)
  }, [fetchAll])

  const totalMemories = statsMap.reduce((sum, s) => sum + (s.status?.total_memories ?? 0), 0)

  if (offline) {
    return (
      <div style={{ padding: '32px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '16px 20px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '8px',
            color: '#ef4444',
          }}
        >
          <WifiOff size={20} />
          <div>
            <div style={{ fontWeight: 600 }}>Agent Offline</div>
            <div style={{ fontSize: '13px', opacity: 0.8 }}>
              Cannot connect to the Memento backend. Make sure the agent is running.
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '32px', maxWidth: '1200px' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3', margin: 0 }}>
          System Dashboard
        </h1>
        {lastUpdated && (
          <p style={{ fontSize: '13px', color: '#8B949E', marginTop: '4px' }}>
            Last updated: {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </div>

      {/* System Health */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#8B949E', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          System Health
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
          <Card>
            <CardContent style={{ paddingTop: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ padding: '10px', backgroundColor: 'rgba(124, 58, 237, 0.15)', borderRadius: '8px' }}>
                  <Database size={20} style={{ color: '#7C3AED' }} />
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: '#e6edf3' }}>
                    {statsMap.length}
                  </div>
                  <div style={{ fontSize: '13px', color: '#8B949E' }}>Datasources</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent style={{ paddingTop: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ padding: '10px', backgroundColor: 'rgba(16, 185, 129, 0.15)', borderRadius: '8px' }}>
                  <Brain size={20} style={{ color: '#10B981' }} />
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: '#e6edf3' }}>
                    {totalMemories}
                  </div>
                  <div style={{ fontSize: '13px', color: '#8B949E' }}>Total Memories</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent style={{ paddingTop: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ padding: '10px', backgroundColor: 'rgba(6, 182, 212, 0.15)', borderRadius: '8px' }}>
                  <Layers size={20} style={{ color: '#06B6D4' }} />
                </div>
                <div>
                  <div style={{ fontSize: '28px', fontWeight: 700, color: '#e6edf3' }}>
                    {statsMap.reduce((sum, s) => sum + (s.status?.consolidations ?? 0), 0)}
                  </div>
                  <div style={{ fontSize: '13px', color: '#8B949E' }}>Total Consolidations</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Per-datasource cards */}
      {statsMap.length > 0 && (
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#8B949E', marginBottom: '16px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Datasources
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {statsMap.map(({ datasource, status, error }) => (
              <Link
                key={datasource.name}
                to="/datasource/$name"
                params={{ name: datasource.name }}
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
              <Card style={{ cursor: 'pointer', transition: 'border-color 0.15s' }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#7C3AED' }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = '' }}
              >
                <CardHeader style={{ paddingBottom: '8px' }}>
                  <CardTitle style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: 'monospace', fontSize: '15px' }}>{datasource.name}</span>
                    {!datasource.inbox_exists && (
                      <Badge variant="warning" style={{ fontSize: '11px' }}>
                        <AlertTriangle size={10} style={{ marginRight: '4px' }} />
                        No Inbox
                      </Badge>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {error ? (
                    <p style={{ color: '#ef4444', fontSize: '13px' }}>{error}</p>
                  ) : status ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
                        <span style={{ color: '#8B949E' }}>Memories</span>
                        <span style={{ color: '#e6edf3', fontWeight: 600 }}>{status.total_memories}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
                        <span style={{ color: '#8B949E' }}>Unconsolidated</span>
                        <span style={{ color: status.unconsolidated > 0 ? '#F59E0B' : '#10B981', fontWeight: 600 }}>
                          {status.unconsolidated}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px' }}>
                        <span style={{ color: '#8B949E' }}>Consolidations</span>
                        <span style={{ color: '#e6edf3', fontWeight: 600 }}>{status.consolidations}</span>
                      </div>
                      {status.warning && (
                        <div style={{ fontSize: '12px', color: '#F59E0B', marginTop: '4px' }}>
                          <AlertTriangle size={12} style={{ display: 'inline', marginRight: '4px' }} />
                          {status.warning}
                        </div>
                      )}
                    </div>
                  ) : (
                    <p style={{ color: '#8B949E', fontSize: '13px' }}>Loading...</p>
                  )}
                </CardContent>
              </Card>
              </Link>
            ))}
          </div>
        </div>
      )}

      {statsMap.length === 0 && !offline && (
        <Card>
          <CardContent style={{ padding: '32px', textAlign: 'center' }}>
            <Database size={40} style={{ color: '#8B949E', margin: '0 auto 16px' }} />
            <p style={{ color: '#8B949E', margin: 0 }}>
              No datasources found. Create one in the Datasources page.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
