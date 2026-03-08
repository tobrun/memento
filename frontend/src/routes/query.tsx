import { createFileRoute } from '@tanstack/react-router'
import { QueryPage } from '@/pages/QueryPage'

export const Route = createFileRoute('/query')({
  component: QueryPage,
})
