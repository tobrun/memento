import { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from '@tanstack/react-router'
import {
  fetchStatus,
  fetchMemories,
  fetchFiles,
  type StatusResponse,
  type Memory,
  type InboxFile,
} from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Database, FileText, Brain, ChevronDown, ChevronRight, Download } from 'lucide-react'

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

function formatTimestamp(epoch: number): string {
  return new Date(epoch * 1000).toLocaleString()
}

export function DatasourceDetailPage() {
  const { name } = useParams({ from: '/datasource/$name' })
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [memories, setMemories] = useState<Memory[]>([])
  const [files, setFiles] = useState<InboxFile[]>([])
  const [expandedMemory, setExpandedMemory] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<'memories' | 'files'>('memories')
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    try {
      const [statusRes, memoriesRes, filesRes] = await Promise.all([
        fetchStatus(name),
        fetchMemories(name, undefined, 100),
        fetchFiles(name),
      ])
      setStatus(statusRes)
      setMemories(memoriesRes.memories)
      setFiles(filesRes.files)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load datasource')
    }
  }, [name])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const tabStyle = (active: boolean) => ({
    padding: '8px 16px',
    fontSize: '14px',
    fontWeight: 600 as const,
    color: active ? '#e6edf3' : '#8B949E',
    backgroundColor: active ? '#21262D' : 'transparent',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer' as const,
  })

  return (
    <div style={{ padding: '32px', maxWidth: '1200px' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <Link
          to="/dashboard"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '13px',
            color: '#8B949E',
            textDecoration: 'none',
            marginBottom: '12px',
          }}
        >
          <ArrowLeft size={14} />
          Back to Dashboard
        </Link>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3', margin: 0, fontFamily: 'monospace' }}>
          {name}
        </h1>
      </div>

      {error && (
        <Card style={{ marginBottom: '24px' }}>
          <CardContent style={{ padding: '16px', color: '#ef4444' }}>{error}</CardContent>
        </Card>
      )}

      {/* Stats row */}
      {status && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
          <Card>
            <CardContent style={{ paddingTop: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ padding: '8px', backgroundColor: 'rgba(124, 58, 237, 0.15)', borderRadius: '8px' }}>
                  <Brain size={18} style={{ color: '#7C3AED' }} />
                </div>
                <div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3' }}>{status.total_memories}</div>
                  <div style={{ fontSize: '12px', color: '#8B949E' }}>Memories</div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent style={{ paddingTop: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ padding: '8px', backgroundColor: 'rgba(245, 158, 11, 0.15)', borderRadius: '8px' }}>
                  <Database size={18} style={{ color: '#F59E0B' }} />
                </div>
                <div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3' }}>{status.unconsolidated}</div>
                  <div style={{ fontSize: '12px', color: '#8B949E' }}>Unconsolidated</div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent style={{ paddingTop: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ padding: '8px', backgroundColor: 'rgba(6, 182, 212, 0.15)', borderRadius: '8px' }}>
                  <FileText size={18} style={{ color: '#06B6D4' }} />
                </div>
                <div>
                  <div style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3' }}>{files.length}</div>
                  <div style={{ fontSize: '12px', color: '#8B949E' }}>Inbox Files</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '16px', padding: '4px', backgroundColor: '#0D1117', borderRadius: '8px', width: 'fit-content' }}>
        <button style={tabStyle(activeTab === 'memories')} onClick={() => setActiveTab('memories')}>
          Memories ({memories.length})
        </button>
        <button style={tabStyle(activeTab === 'files')} onClick={() => setActiveTab('files')}>
          Inbox Files ({files.length})
        </button>
      </div>

      {/* Memories tab */}
      {activeTab === 'memories' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {memories.length === 0 && (
            <Card>
              <CardContent style={{ padding: '32px', textAlign: 'center', color: '#8B949E' }}>
                No memories stored yet.
              </CardContent>
            </Card>
          )}
          {memories.map((memory) => {
            const isExpanded = expandedMemory === memory.id
            return (
              <Card key={memory.id}>
                <CardHeader
                  style={{ cursor: 'pointer', paddingBottom: isExpanded ? '8px' : '16px' }}
                  onClick={() => setExpandedMemory(isExpanded ? null : memory.id)}
                >
                  <CardTitle style={{ fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {isExpanded
                      ? <ChevronDown size={14} style={{ color: '#8B949E', flexShrink: 0 }} />
                      : <ChevronRight size={14} style={{ color: '#8B949E', flexShrink: 0 }} />}
                    <span style={{ fontFamily: 'monospace', color: '#7C3AED', fontSize: '12px', flexShrink: 0 }}>
                      #{memory.id}
                    </span>
                    <span style={{ color: '#e6edf3', fontWeight: 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {memory.summary}
                    </span>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px', flexShrink: 0 }}>
                      <Badge
                        variant={memory.importance >= 0.7 ? 'default' : memory.importance >= 0.4 ? 'warning' : 'secondary'}
                        style={{ fontSize: '10px', padding: '1px 6px' }}
                      >
                        {Math.round(memory.importance * 10)}/10
                      </Badge>
                      {memory.consolidated && (
                        <Badge variant="success" style={{ fontSize: '10px', padding: '1px 6px' }}>
                          consolidated
                        </Badge>
                      )}
                    </div>
                  </CardTitle>
                </CardHeader>
                {isExpanded && (
                  <CardContent style={{ paddingTop: 0 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {/* Metadata */}
                      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '12px', color: '#8B949E' }}>
                        {memory.source && (
                          <span>
                            Source:{' '}
                            <a
                              href={`/api/download/${encodeURIComponent(name)}/${encodeURIComponent(memory.source)}`}
                              download
                              style={{ color: '#06B6D4', textDecoration: 'none' }}
                            >
                              {memory.source}
                            </a>
                          </span>
                        )}
                        <span>Created: {formatDate(memory.created_at)}</span>
                      </div>

                      {/* Entities & Topics */}
                      {(memory.entities.length > 0 || memory.topics.length > 0) && (
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {memory.entities.map((e) => (
                            <Badge key={e} variant="secondary" style={{ fontSize: '11px' }}>{e}</Badge>
                          ))}
                          {memory.topics.map((t) => (
                            <Badge key={t} style={{ fontSize: '11px', backgroundColor: 'rgba(6, 182, 212, 0.15)', color: '#06B6D4' }}>{t}</Badge>
                          ))}
                        </div>
                      )}

                      {/* Raw text */}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#8B949E', marginBottom: '6px' }}>Raw Content</div>
                        <pre style={{
                          padding: '12px',
                          backgroundColor: '#0D1117',
                          border: '1px solid #21262D',
                          borderRadius: '6px',
                          fontSize: '12px',
                          color: '#8B949E',
                          lineHeight: '1.5',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          maxHeight: '300px',
                          overflowY: 'auto',
                          margin: 0,
                        }}>
                          {memory.raw_text}
                        </pre>
                      </div>
                    </div>
                  </CardContent>
                )}
              </Card>
            )
          })}
        </div>
      )}

      {/* Files tab */}
      {activeTab === 'files' && (
        <Card>
          <CardContent style={{ padding: files.length === 0 ? '32px' : '0' }}>
            {files.length === 0 && (
              <p style={{ textAlign: 'center', color: '#8B949E', margin: 0 }}>
                No files in inbox.
              </p>
            )}
            {files.length > 0 && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #21262D' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', color: '#8B949E', fontWeight: 600 }}>Name</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right', color: '#8B949E', fontWeight: 600 }}>Size</th>
                    <th style={{ padding: '12px 16px', textAlign: 'right', color: '#8B949E', fontWeight: 600 }}>Modified</th>
                    <th style={{ padding: '12px 16px', width: '48px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr key={file.name} style={{ borderBottom: '1px solid #21262D' }}>
                      <td style={{ padding: '10px 16px', color: '#e6edf3', fontFamily: 'monospace' }}>{file.name}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', color: '#8B949E' }}>{formatBytes(file.size)}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'right', color: '#8B949E' }}>{formatTimestamp(file.modified)}</td>
                      <td style={{ padding: '10px 16px', textAlign: 'center' }}>
                        <a
                          href={`/api/download/${encodeURIComponent(name)}/${encodeURIComponent(file.name)}`}
                          download
                          style={{ color: '#06B6D4' }}
                        >
                          <Download size={14} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
