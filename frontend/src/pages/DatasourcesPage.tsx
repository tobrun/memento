import { useState, useEffect } from 'react'
import { fetchDatasources, createDatasource, clearDatasource, consolidate, type Datasource } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Database, Plus, Trash2, AlertTriangle, CheckCircle, AlertCircle, Loader2, GitMerge } from 'lucide-react'

const NAME_PATTERN = /^[a-z0-9_-]+$/

export function DatasourcesPage() {
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [newName, setNewName] = useState('')
  const [nameError, setNameError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [createMessage, setCreateMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const [clearingDs, setClearingDs] = useState<string | null>(null)
  const [consolidatingDs, setConsolidatingDs] = useState<string | null>(null)

  const loadDatasources = async () => {
    try {
      const data = await fetchDatasources()
      setDatasources(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load datasources')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDatasources()
  }, [])

  const validateName = (name: string): string | null => {
    if (!name) return 'Name is required'
    if (!NAME_PATTERN.test(name)) {
      return 'Name must contain only lowercase letters, numbers, hyphens, and underscores'
    }
    return null
  }

  const handleNameChange = (value: string) => {
    setNewName(value)
    setNameError(validateName(value))
  }

  const handleCreate = async () => {
    const validationError = validateName(newName)
    if (validationError) {
      setNameError(validationError)
      return
    }
    setCreating(true)
    setCreateMessage(null)
    try {
      await createDatasource(newName)
      setCreateMessage({ type: 'success', text: `Datasource "${newName}" created successfully` })
      setNewName('')
      setNameError(null)
      await loadDatasources()
    } catch (err) {
      setCreateMessage({ type: 'error', text: err instanceof Error ? err.message : 'Failed to create datasource' })
    } finally {
      setCreating(false)
    }
  }

  const handleConsolidate = async (name: string) => {
    setConsolidatingDs(name)
    try {
      await consolidate(name)
      await loadDatasources()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to consolidate "${name}"`)
    } finally {
      setConsolidatingDs(null)
    }
  }

  const handleClear = async (name: string) => {
    setClearingDs(name)
    try {
      await clearDatasource(name)
      await loadDatasources()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to clear datasource "${name}"`)
    } finally {
      setClearingDs(null)
    }
  }

  return (
    <div style={{ padding: '32px', maxWidth: '1000px' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3', margin: 0 }}>Datasources</h1>
        <p style={{ fontSize: '14px', color: '#8B949E', marginTop: '4px' }}>
          Manage your isolated memory stores
        </p>
      </div>

      {/* Create datasource */}
      <Card style={{ marginBottom: '32px' }}>
        <CardHeader style={{ paddingBottom: '12px' }}>
          <CardTitle style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px' }}>
            <Plus size={16} style={{ color: '#7C3AED' }} />
            Create Datasource
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <div style={{ flex: 1 }}>
              <Input
                value={newName}
                onChange={(e) => handleNameChange(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') void handleCreate() }}
                placeholder="e.g. news, company-docs, research"
              />
              {nameError && (
                <p style={{ fontSize: '12px', color: '#ef4444', marginTop: '6px', marginBottom: 0 }}>
                  {nameError}
                </p>
              )}
            </div>
            <Button
              onClick={() => void handleCreate()}
              disabled={creating || !!nameError || !newName}
              style={{ flexShrink: 0 }}
            >
              {creating ? <><Loader2 size={16} className="animate-spin" /> Creating...</> : 'Create'}
            </Button>
          </div>

          {createMessage && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '12px',
                padding: '10px 12px',
                borderRadius: '6px',
                fontSize: '14px',
                backgroundColor: createMessage.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${createMessage.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                color: createMessage.type === 'success' ? '#10B981' : '#ef4444',
              }}
            >
              {createMessage.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              {createMessage.text}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Datasource table */}
      {error && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px',
            marginBottom: '16px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '6px',
            color: '#ef4444',
            fontSize: '14px',
          }}
        >
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#8B949E' }}>
          <Loader2 size={20} className="animate-spin" />
          Loading datasources...
        </div>
      ) : datasources.length === 0 ? (
        <Card>
          <CardContent style={{ padding: '40px', textAlign: 'center' }}>
            <Database size={40} style={{ color: '#8B949E', margin: '0 auto 16px' }} />
            <p style={{ color: '#8B949E', margin: 0 }}>No datasources yet. Create your first one above.</p>
          </CardContent>
        </Card>
      ) : (
        <div
          style={{
            border: '1px solid #21262D',
            borderRadius: '8px',
            overflow: 'hidden',
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 120px 120px 120px 210px',
              padding: '12px 16px',
              backgroundColor: '#161B22',
              borderBottom: '1px solid #21262D',
              fontSize: '12px',
              color: '#8B949E',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
            }}
          >
            <span>Name</span>
            <span>Memories</span>
            <span>Unconsolidated</span>
            <span>Inbox</span>
            <span>Actions</span>
          </div>

          {/* Table rows */}
          {datasources.map((ds, index) => (
            <div
              key={ds.name}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 120px 120px 120px 210px',
                padding: '14px 16px',
                alignItems: 'center',
                borderBottom: index < datasources.length - 1 ? '1px solid #21262D' : 'none',
                backgroundColor: '#0D1117',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Database size={14} style={{ color: '#7C3AED', flexShrink: 0 }} />
                <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#e6edf3' }}>{ds.name}</span>
              </div>
              <span style={{ color: '#e6edf3', fontWeight: 500 }}>{ds.total_memories}</span>
              <span style={{ color: ds.unconsolidated > 0 ? '#F59E0B' : '#8B949E' }}>
                {ds.unconsolidated}
              </span>
              <span>
                {ds.inbox_exists ? (
                  <Badge variant="success" style={{ fontSize: '11px' }}>Active</Badge>
                ) : (
                  <Badge variant="warning" style={{ fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                    <AlertTriangle size={10} />
                    Missing
                  </Badge>
                )}
              </span>
              <div style={{ display: 'flex', gap: '4px' }}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void handleConsolidate(ds.name)}
                  disabled={consolidatingDs === ds.name}
                  style={{ color: '#7C3AED', padding: '4px 8px' }}
                >
                  {consolidatingDs === ds.name ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <GitMerge size={14} />
                  )}
                  {consolidatingDs === ds.name ? 'Running...' : 'Consolidate'}
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={clearingDs === ds.name}
                      style={{ color: '#ef4444', padding: '4px 8px' }}
                    >
                      {clearingDs === ds.name ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Trash2 size={14} />
                      )}
                      {clearingDs === ds.name ? 'Clearing...' : 'Clear'}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Clear datasource "{ds.name}"?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently delete all memories, consolidations, and inbox files
                        for the <strong style={{ color: '#e6edf3' }}>{ds.name}</strong> datasource.
                        This action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => void handleClear(ds.name)}
                        style={{ backgroundColor: '#ef4444' }}
                      >
                        Clear All Data
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
