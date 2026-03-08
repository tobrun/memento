import { createFileRoute } from '@tanstack/react-router'
import { DatasourcesPage } from '@/pages/DatasourcesPage'

export const Route = createFileRoute('/datasources')({
  component: DatasourcesPage,
})
