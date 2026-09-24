import * as React from "react"
import { cn } from "@/lib/utils"

export type ChartConfig = {
  [k in string]: {
    label?: React.ReactNode
    icon?: React.ComponentType
    color?: string
  }
}

export function ChartContainer({
  className,
  children,
  config,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { config?: ChartConfig }) {
  return (
    <div className={cn("w-full h-full", className)} {...props}>
      {children}
    </div>
  )
}

export function ChartTooltip({ children }: { children?: React.ReactNode }) {
  return <div className="p-2 rounded bg-black/80 text-white text-xs">{children}</div>
}

export function ChartTooltipContent({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: any[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-background p-2 shadow-sm">
      {label && <div className="font-semibold text-xs mb-1">{label}</div>}
      {payload.map((item, index) => (
        <div key={index} className="text-xs text-muted-foreground flex items-center gap-2">
          <span>{item.name}:</span>
          <span className="font-mono font-bold text-foreground">{item.value}</span>
        </div>
      ))}
    </div>
  )
}

export function ChartLegend({ children }: { children?: React.ReactNode }) {
  return <div className="flex gap-2 text-xs">{children}</div>
}

export function ChartLegendContent() {
  return null
}

export function ChartStyle() {
  return null
}
