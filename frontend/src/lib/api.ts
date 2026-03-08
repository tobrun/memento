export interface Datasource {
  name: string
  total_memories: number
  unconsolidated: number
  inbox_exists: boolean
  warning?: string
}

export interface Memory {
  id: number
  source: string
  source_file: string | null
  summary: string
  entities: string[]
  topics: string[]
  importance: number
  connections: { linked_to: number; relationship: string }[]
  created_at: string
  consolidated: boolean
}

export interface MemoriesResponse {
  memories: Memory[]
  next_cursor: number | null
}

export interface StatusResponse {
  total_memories: number
  unconsolidated: number
  consolidations: number
  warning?: string
}

const BASE = '/api'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`
    try {
      const data = await res.json() as { error?: string; message?: string }
      message = data.error ?? data.message ?? message
    } catch {
      // ignore parse errors
    }
    throw new Error(message)
  }
  return res.json() as Promise<T>
}

export async function fetchDatasources(): Promise<Datasource[]> {
  const res = await fetch(`${BASE}/datasources`)
  return handleResponse<Datasource[]>(res)
}

export async function createDatasource(name: string): Promise<{ status: string; name: string }> {
  const res = await fetch(`${BASE}/datasources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  return handleResponse<{ status: string; name: string }>(res)
}

export async function queryMemories(
  datasource: string,
  question: string,
): Promise<{ question: string; answer: string; warning?: string }> {
  const params = new URLSearchParams({ q: question })
  const res = await fetch(`${BASE}/query/${encodeURIComponent(datasource)}?${params}`)
  return handleResponse<{ question: string; answer: string; warning?: string }>(res)
}

export async function ingestText(
  datasource: string,
  text: string,
  source?: string,
): Promise<{ status: string; response: string }> {
  const res = await fetch(`${BASE}/ingest/${encodeURIComponent(datasource)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, source }),
  })
  return handleResponse<{ status: string; response: string }>(res)
}

export async function fetchSupportedFormats(): Promise<{ extensions: string[] }> {
  const res = await fetch(`${BASE}/supported-formats`)
  return handleResponse<{ extensions: string[] }>(res)
}

export async function uploadFile(
  datasource: string,
  file: File,
): Promise<{ status: string; filename: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE}/upload/${encodeURIComponent(datasource)}`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<{ status: string; filename: string }>(res)
}

export async function fetchMemories(
  datasource: string,
  cursor?: number,
  limit?: number,
): Promise<MemoriesResponse> {
  const params = new URLSearchParams()
  if (cursor !== undefined) params.set('cursor', String(cursor))
  if (limit !== undefined) params.set('limit', String(limit))
  const query = params.toString() ? `?${params}` : ''
  const res = await fetch(`${BASE}/memories/${encodeURIComponent(datasource)}${query}`)
  return handleResponse<MemoriesResponse>(res)
}

export async function fetchStatus(datasource: string): Promise<StatusResponse> {
  const res = await fetch(`${BASE}/status/${encodeURIComponent(datasource)}`)
  return handleResponse<StatusResponse>(res)
}

export async function consolidate(datasource: string): Promise<{ status: string; response: string }> {
  const res = await fetch(`${BASE}/consolidate/${encodeURIComponent(datasource)}`, {
    method: 'POST',
  })
  return handleResponse<{ status: string; response: string }>(res)
}

export async function deleteMemory(
  datasource: string,
  memoryId: number,
): Promise<{ status: string }> {
  const res = await fetch(`${BASE}/delete/${encodeURIComponent(datasource)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ memory_id: memoryId }),
  })
  return handleResponse<{ status: string }>(res)
}

export async function clearDatasource(
  datasource: string,
): Promise<{ status: string; memories_deleted: number; files_deleted: number }> {
  const res = await fetch(`${BASE}/clear/${encodeURIComponent(datasource)}`, {
    method: 'POST',
  })
  return handleResponse<{ status: string; memories_deleted: number; files_deleted: number }>(res)
}
