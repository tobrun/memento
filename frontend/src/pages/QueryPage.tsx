import { useState, useEffect } from 'react'
import { fetchDatasources, queryMemories, fetchMemories, type Datasource, type Memory } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Search, BookOpen, Loader2, AlertCircle } from 'lucide-react'
import { marked } from 'marked'

export function QueryPage() {
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [selectedDs, setSelectedDs] = useState<string>('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchDatasources()
      .then((data) => {
        setDatasources(data)
        if (data.length > 0) setSelectedDs(data[0].name)
      })
      .catch(() => {/* silently fail */})
  }, [])

  const handleSearch = async () => {
    if (!selectedDs) {
      setError('Please select a datasource')
      return
    }
    if (!question.trim()) {
      setError('Please enter a question')
      return
    }
    setLoading(true)
    setError(null)
    setAnswer(null)
    setMemories([])

    try {
      const [queryResult, memoriesResult] = await Promise.all([
        queryMemories(selectedDs, question),
        fetchMemories(selectedDs, undefined, 50),
      ])
      setAnswer(queryResult.answer)
      setMemories(memoriesResult.memories)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Query failed')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      void handleSearch()
    }
  }

  const renderedAnswer = answer
    ? marked.parse(answer, { async: false }) as string
    : null

  return (
    <div style={{ padding: '32px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3', margin: 0 }}>Query</h1>
        <p style={{ fontSize: '14px', color: '#8B949E', marginTop: '4px' }}>
          Ask questions across your memory store
        </p>
      </div>

      {/* Search bar */}
      <Card style={{ marginBottom: '24px' }}>
        <CardContent style={{ paddingTop: '20px' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
            <div style={{ width: '200px', flexShrink: 0 }}>
              <label style={{ fontSize: '13px', color: '#8B949E', marginBottom: '6px', display: 'block' }}>
                Datasource
              </label>
              <Select value={selectedDs} onValueChange={setSelectedDs}>
                <SelectTrigger>
                  <SelectValue placeholder="Select..." />
                </SelectTrigger>
                <SelectContent>
                  {datasources.map((ds) => (
                    <SelectItem key={ds.name} value={ds.name}>
                      {ds.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: '13px', color: '#8B949E', marginBottom: '6px', display: 'block' }}>
                Question <span style={{ color: '#8B949E', fontWeight: 400 }}>(Ctrl+Enter to submit)</span>
              </label>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your memories..."
                rows={2}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#0D1117',
                  border: '1px solid #21262D',
                  borderRadius: '6px',
                  color: '#e6edf3',
                  fontSize: '14px',
                  outline: 'none',
                  boxSizing: 'border-box',
                  resize: 'none',
                  fontFamily: 'inherit',
                }}
              />
            </div>
            <Button
              onClick={() => void handleSearch()}
              disabled={loading}
              style={{ alignSelf: 'flex-end', height: '36px', gap: '6px' }}
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
              {loading ? 'Searching...' : 'Search'}
            </Button>
          </div>

          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginTop: '12px',
                padding: '10px 12px',
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
        </CardContent>
      </Card>

      {/* Results area — two column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '24px' }}>
        {/* Left: Answer */}
        <div>
          <Card style={{ minHeight: '400px' }}>
            <CardHeader style={{ paddingBottom: '12px' }}>
              <CardTitle style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Search size={16} style={{ color: '#7C3AED' }} />
                Answer
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#8B949E' }}>
                  <Loader2 size={20} className="animate-spin" />
                  <span>Querying memories...</span>
                </div>
              )}
              {!loading && renderedAnswer && (
                <div
                  className="prose-content"
                  dangerouslySetInnerHTML={{ __html: renderedAnswer }}
                  style={{
                    color: '#e6edf3',
                    fontSize: '14px',
                    lineHeight: '1.7',
                  }}
                />
              )}
              {!loading && !renderedAnswer && !error && (
                <p style={{ color: '#8B949E', fontSize: '14px' }}>
                  Enter a question and click Search to query your memories.
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: Source memories */}
        <div>
          <Card style={{ minHeight: '400px' }}>
            <CardHeader style={{ paddingBottom: '12px' }}>
              <CardTitle style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BookOpen size={16} style={{ color: '#06B6D4' }} />
                Source Memories
                {memories.length > 0 && (
                  <Badge variant="secondary" style={{ marginLeft: 'auto', fontSize: '11px' }}>
                    {memories.length}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {!answer && !loading && (
                <p style={{ color: '#8B949E', fontSize: '13px' }}>
                  Source memories will appear here after a query.
                </p>
              )}
              {memories.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '600px', overflowY: 'auto' }}>
                  {memories.map((memory) => (
                    <div
                      key={memory.id}
                      style={{
                        padding: '10px 12px',
                        backgroundColor: '#0D1117',
                        border: '1px solid #21262D',
                        borderRadius: '6px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span style={{ fontSize: '11px', fontFamily: 'monospace', color: '#7C3AED', fontWeight: 600 }}>
                          #{memory.id}
                        </span>
                        <Badge
                          variant={memory.importance >= 7 ? 'default' : memory.importance >= 4 ? 'warning' : 'secondary'}
                          style={{ fontSize: '10px', padding: '1px 6px' }}
                        >
                          {memory.importance}/10
                        </Badge>
                        {memory.consolidated && (
                          <Badge variant="success" style={{ fontSize: '10px', padding: '1px 6px' }}>
                            consolidated
                          </Badge>
                        )}
                      </div>
                      <p style={{ margin: 0, fontSize: '12px', color: '#8B949E', lineHeight: '1.5' }}>
                        {memory.summary.length > 120
                          ? `${memory.summary.slice(0, 120)}...`
                          : memory.summary}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
