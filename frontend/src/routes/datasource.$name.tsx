import { createFileRoute } from '@tanstack/react-router'
import { DatasourceDetailPage } from '@/pages/DatasourceDetailPage'

export const Route = createFileRoute('/datasource/$name')({
  component: DatasourceDetailPage,
})
