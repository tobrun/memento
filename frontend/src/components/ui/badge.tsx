import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-[#7C3AED] text-white',
        secondary: 'border-transparent bg-[#21262D] text-[#e6edf3]',
        destructive: 'border-transparent bg-red-600 text-white',
        outline: 'border-[#21262D] text-[#e6edf3]',
        success: 'border-transparent bg-[#10B981] text-white',
        warning: 'border-transparent bg-[#F59E0B] text-white',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
