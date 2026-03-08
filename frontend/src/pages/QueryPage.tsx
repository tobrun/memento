import { useState, useEffect, useMemo } from 'react'
import { fetchDatasources, queryMemories, fetchMemories, type Datasource, type Memory } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Search, BookOpen, Loader2, AlertCircle } from 'lucide-react'
import { marked } from 'marked'

/** Extract memory IDs cited in the answer, e.g. [Memory 3], [Memory #12]. */
function parseCitedIds(text: string): Set<number> {
  const ids = new Set<number>()
  const re = /\[Memory\s*#?(\d+)\]/gi
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    ids.add(Number(m[1]))
  }
  return ids
}

export function QueryPage() {
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [selectedDs, setSelectedDs] = useState<string>('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)

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
    setShowAll(false)

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

  const { preamble, body: answerBody, citedIds } = useMemo(() => {
    if (!answer) return { preamble: null, body: null, citedIds: new Set<number>() }
    const html = marked.parse(answer, { async: false }) as string
    const headingIndex = html.search(/<h[1-6][\s>]/)
    if (headingIndex <= 0) return { preamble: null, body: html, citedIds: parseCitedIds(answer) }
    const before = html.slice(0, headingIndex).trim()
    // Split raw markdown at the first heading to extract only body citations
    const mdHeadingIndex = answer.search(/^#{1,6}\s/m)
    const bodyMd = mdHeadingIndex > 0 ? answer.slice(mdHeadingIndex) : answer
    if (!before) return { preamble: null, body: html, citedIds: parseCitedIds(bodyMd) }
    return { preamble: before, body: html.slice(headingIndex), citedIds: parseCitedIds(bodyMd) }
  }, [answer])

  const displayedMemories = useMemo(() => {
    if (showAll || citedIds.size === 0) return memories
    return memories.filter((m) => citedIds.has(m.id))
  }, [memories, citedIds, showAll])

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
              {!loading && answerBody && (
                <div className="prose-content" style={{ color: '#e6edf3', fontSize: '14px', lineHeight: '1.7' }}>
                  {preamble && (
                    <details style={{
                      marginBottom: '16px',
                      padding: '8px 12px',
                      backgroundColor: 'rgba(124, 58, 237, 0.05)',
                      border: '1px solid #21262D',
                      borderRadius: '6px',
                    }}>
                      <summary style={{
                        cursor: 'pointer',
                        fontSize: '12px',
                        color: '#8B949E',
                        userSelect: 'none',
                      }}>
                        Reasoning
                      </summary>
                      <div
                        dangerouslySetInnerHTML={{ __html: preamble }}
                        style={{ marginTop: '8px', fontSize: '13px', color: '#8B949E', lineHeight: '1.6' }}
                      />
                    </details>
                  )}
                  <div dangerouslySetInnerHTML={{ __html: answerBody }} />
                </div>
              )}
              {!loading && !answerBody && !error && (
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
                {showAll ? 'All Memories' : 'Cited Memories'}
                {displayedMemories.length > 0 && (
                  <Badge variant="secondary" style={{ marginLeft: 'auto', fontSize: '11px' }}>
                    {displayedMemories.length}{!showAll && memories.length > 0 ? `/${memories.length}` : ''}
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
              {answer && memories.length > 0 && (
                <>
                  <button
                    onClick={() => setShowAll((prev) => !prev)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#7C3AED',
                      fontSize: '12px',
                      cursor: 'pointer',
                      padding: '0 0 8px 0',
                      textDecoration: 'underline',
                    }}
                  >
                    {showAll ? 'Show cited only' : 'Show all memories'}
                  </button>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '600px', overflowY: 'auto' }}>
                    {displayedMemories.map((memory) => (
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
                        <p style={{ margin: 0, fontSize: '12px', color: '#8B949E', lineHeight: '1.5' }}>
                          {memory.summary.length > 120
                            ? `${memory.summary.slice(0, 120)}...`
                            : memory.summary}
                        </p>
                        {memory.source && (
                          <a
                            href={`/api/download/${encodeURIComponent(selectedDs)}/${encodeURIComponent(memory.source)}`}
                            download
                            style={{
                              display: 'inline-block',
                              marginTop: '6px',
                              fontSize: '11px',
                              color: '#06B6D4',
                              textDecoration: 'none',
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.textDecoration = 'underline' }}
                            onMouseLeave={(e) => { e.currentTarget.style.textDecoration = 'none' }}
                          >
                            {memory.source}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
              {answer && displayedMemories.length === 0 && (
                <p style={{ color: '#8B949E', fontSize: '13px' }}>
                  No memory citations found in the answer.
                  {' '}
                  <button
                    onClick={() => setShowAll(true)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#7C3AED',
                      fontSize: '13px',
                      cursor: 'pointer',
                      padding: 0,
                      textDecoration: 'underline',
                    }}
                  >
                    Show all memories
                  </button>
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
