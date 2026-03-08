import { createFileRoute } from '@tanstack/react-router'
import { IngestPage } from '@/pages/IngestPage'

export const Route = createFileRoute('/ingest')({
  component: IngestPage,
})
