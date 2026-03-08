import { useState, useEffect, useRef, type DragEvent } from 'react'
import { fetchDatasources, fetchSupportedFormats, uploadFile, type Datasource } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Upload, CheckCircle, AlertCircle, Loader2, X } from 'lucide-react'

type FileStatus = 'pending' | 'uploading' | 'done' | 'error'
interface FileEntry { file: File; status: FileStatus; message?: string }

export function IngestPage() {
  const [datasources, setDatasources] = useState<Datasource[]>([])
  const [selectedDs, setSelectedDs] = useState<string>('')

  const [fileEntries, setFileEntries] = useState<FileEntry[]>([])
  const [fileLoading, setFileLoading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)
  const [supportedExtensions, setSupportedExtensions] = useState<Set<string>>(new Set())
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchSupportedFormats()
      .then((data) => setSupportedExtensions(new Set(data.extensions)))
      .catch(() => {/* silently fail — backend validation still applies */})
  }, [])

  const addFiles = (incoming: File[]) => {
    const entries: FileEntry[] = incoming.map((file) => {
      if (supportedExtensions.size > 0) {
        const ext = file.name.includes('.') ? `.${file.name.split('.').pop()!.toLowerCase()}` : ''
        if (!supportedExtensions.has(ext)) {
          return { file, status: 'error' as FileStatus, message: `Unsupported file type: ${ext || '(no extension)'}` }
        }
      }
      return { file, status: 'pending' as FileStatus }
    })
    setFileEntries((prev) => [...prev, ...entries])
  }

  const removeFile = (index: number) => {
    setFileEntries((prev) => prev.filter((_, i) => i !== index))
  }

  useEffect(() => {
    fetchDatasources()
      .then((data) => {
        setDatasources(data)
        if (data.length > 0 && !selectedDs) {
          setSelectedDs(data[0].name)
        }
      })
      .catch(() => {/* silently fail */})
  }, [selectedDs])

  const handleFileUpload = async () => {
    if (!selectedDs) return
    const pending = fileEntries.filter((e) => e.status === 'pending')
    if (pending.length === 0) return
    setFileLoading(true)
    for (const entry of pending) {
      const file = entry.file
      setFileEntries((prev) =>
        prev.map((e) => e.file === file ? { ...e, status: 'uploading' } : e)
      )
      try {
        await uploadFile(selectedDs, file)
        setFileEntries((prev) =>
          prev.map((e) => e.file === file ? { ...e, status: 'done' } : e)
        )
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Upload failed'
        setFileEntries((prev) =>
          prev.map((e) => e.file === file ? { ...e, status: 'error', message } : e)
        )
      }
    }
    setFileLoading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(false)
    const dropped = Array.from(e.dataTransfer.files)
    if (dropped.length > 0) addFiles(dropped)
  }

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = () => setIsDragOver(false)

  const dsSelector = (
    <div>
      <label style={{ fontSize: '13px', color: '#8B949E', marginBottom: '6px', display: 'block' }}>
        Datasource
      </label>
      <Select value={selectedDs} onValueChange={setSelectedDs}>
        <SelectTrigger>
          <SelectValue placeholder="Select a datasource..." />
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
  )

  return (
    <div style={{ padding: '32px', maxWidth: '900px' }}>
      <div style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#e6edf3', margin: 0 }}>Ingest</h1>
        <p style={{ fontSize: '14px', color: '#8B949E', marginTop: '4px' }}>
          Upload files to a datasource memory store
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <Card>
          <CardHeader>
            <CardTitle style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Upload size={18} style={{ color: '#06B6D4' }} />
              File Upload
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {dsSelector}

              {/* Drop zone */}
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => fileInputRef.current?.click()}
                style={{
                  border: `2px dashed ${isDragOver ? '#7C3AED' : '#21262D'}`,
                  borderRadius: '8px',
                  padding: '24px 32px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  backgroundColor: isDragOver ? 'rgba(124, 58, 237, 0.05)' : 'transparent',
                  transition: 'all 0.2s ease',
                }}
              >
                <Upload size={28} style={{ color: '#8B949E', margin: '0 auto 10px' }} />
                <p style={{ color: '#e6edf3', margin: '0 0 4px', fontWeight: 500 }}>
                  Drop files here or click to browse
                </p>
                <p style={{ color: '#8B949E', fontSize: '13px', margin: 0 }}>
                  {supportedExtensions.size > 0
                    ? `Supported: ${[...supportedExtensions].join(', ')} (max 20MB each)`
                    : 'Supports text, images, audio, video, PDF (max 20MB each)'}
                </p>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                style={{ display: 'none' }}
                onChange={(e) => {
                  const files = Array.from(e.target.files ?? [])
                  if (files.length > 0) addFiles(files)
                }}
              />

              {/* File list */}
              {fileEntries.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {fileEntries.map((entry, i) => (
                    <div
                      key={i}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '8px 12px',
                        backgroundColor: '#0D1117',
                        border: '1px solid #21262D',
                        borderRadius: '6px',
                        fontSize: '13px',
                      }}
                    >
                      {entry.status === 'uploading' && <Loader2 size={14} className="animate-spin" style={{ color: '#7C3AED', flexShrink: 0 }} />}
                      {entry.status === 'done' && <CheckCircle size={14} style={{ color: '#10B981', flexShrink: 0 }} />}
                      {entry.status === 'error' && <AlertCircle size={14} style={{ color: '#ef4444', flexShrink: 0 }} />}
                      {entry.status === 'pending' && <div style={{ width: 14, height: 14, flexShrink: 0 }} />}
                      <span style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        color: entry.status === 'done' ? '#10B981' : entry.status === 'error' ? '#ef4444' : '#e6edf3',
                      }}>
                        {entry.file.name}
                        {entry.status === 'error' && entry.message && (
                          <span style={{ fontSize: '12px', marginLeft: '6px', opacity: 0.8 }}>
                            — {entry.message}
                          </span>
                        )}
                      </span>
                      <span style={{ color: '#8B949E', flexShrink: 0 }}>
                        {(entry.file.size / 1024).toFixed(1)} KB
                      </span>
                      {entry.status !== 'uploading' && (
                        <button
                          onClick={(ev) => { ev.stopPropagation(); removeFile(i) }}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: '#8B949E', flexShrink: 0, display: 'flex' }}
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <Button
                onClick={() => void handleFileUpload()}
                disabled={fileLoading || fileEntries.filter(e => e.status === 'pending').length === 0}
                variant="secondary"
                style={{ alignSelf: 'flex-start' }}
              >
                {fileLoading
                  ? <><Loader2 size={16} className="animate-spin" /> Uploading...</>
                  : fileEntries.filter(e => e.status === 'pending').length > 1
                    ? `Upload ${fileEntries.filter(e => e.status === 'pending').length} files`
                    : 'Upload'
                }
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
