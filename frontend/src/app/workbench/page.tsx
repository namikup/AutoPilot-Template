'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { cn } from '@/lib/utils'
import { apiClient } from '@/lib/api-client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface WorkbenchItem {
  id: number
  ticket_key: string
  summary: string
  reporter_email: string | null
  reporter_name: string | null
  vip_user: boolean
  organization: string | null
  priority: string | null
  diagnosis: string | null
  proposed_action: string | null
  kb_article_id: string | null
  status: string
  created_at: string
}

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
  exit: { opacity: 0, x: -40, transition: { duration: 0.25 } },
}

// ---------------------------------------------------------------------------
// Priority badge
// ---------------------------------------------------------------------------

function PriorityBadge({ priority }: { priority: string | null }) {
  const styles: Record<string, string> = {
    Highest: 'bg-red-100 text-red-700 border-red-200',
    High: 'bg-orange-100 text-orange-700 border-orange-200',
    Medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    Low: 'bg-green-100 text-green-700 border-green-200',
  }
  const label = priority ?? 'Unknown'
  return (
    <span
      className={cn(
        'rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
        styles[label] ?? 'bg-muted text-muted-foreground border-transparent'
      )}
    >
      {label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Single ticket card
// ---------------------------------------------------------------------------

interface TicketCardProps {
  item: WorkbenchItem
  onApprove: (id: number) => void
  onReject: (id: number) => void
  loading: boolean
}

function TicketCard({ item, onApprove, onReject, loading }: TicketCardProps) {
  return (
    <motion.div variants={itemVariants} exit="exit" layout>
      <Card className="overflow-hidden border-l-4 border-l-amber-400 shadow-sm transition-shadow hover:shadow-md">
        <CardHeader className="pb-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            {/* Left: ticket key + badges */}
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-bold text-brand-navy">
                {item.ticket_key}
              </span>
              <PriorityBadge priority={item.priority} />
              {item.vip_user && (
                <span className="rounded-full border border-purple-200 bg-purple-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-purple-700">
                  ⭐ VIP
                </span>
              )}
              {item.organization && (
                <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-600">
                  {item.organization}
                </span>
              )}
            </div>

            {/* Right: KB article */}
            {item.kb_article_id && (
              <span className="rounded border border-dashed border-slate-300 bg-slate-50 px-2 py-0.5 text-[10px] font-mono text-slate-500">
                {item.kb_article_id}
              </span>
            )}
          </div>

          <CardTitle className="mt-2 text-base">{item.summary}</CardTitle>
          {item.reporter_name && (
            <CardDescription className="text-xs">
              Reported by {item.reporter_name}
              {item.reporter_email ? ` · ${item.reporter_email}` : ''}
            </CardDescription>
          )}
        </CardHeader>

        <CardContent className="space-y-4 pt-0">
          {/* Diagnosis */}
          {item.diagnosis && (
            <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                AI Diagnosis
              </p>
              <p className="leading-relaxed">{item.diagnosis}</p>
            </div>
          )}

          {/* Proposed action */}
          {item.proposed_action && (
            <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-blue-400">
                Proposed Action
              </p>
              <p className="leading-relaxed">{item.proposed_action}</p>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex gap-3 pt-1">
            <Button
              id={`approve-${item.id}`}
              className="flex-1 bg-emerald-600 text-white hover:bg-emerald-700"
              disabled={loading}
              onClick={() => onApprove(item.id)}
            >
              <Icons.check className="mr-2 h-4 w-4" />
              Approve
            </Button>
            <Button
              id={`reject-${item.id}`}
              variant="outline"
              className="flex-1 border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300"
              disabled={loading}
              onClick={() => onReject(item.id)}
            >
              <Icons.close className="mr-2 h-4 w-4" />
              Reject
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function WorkbenchPage() {
  const [items, setItems] = useState<WorkbenchItem[]>([])
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  // ── Fetch pending items ──────────────────────────────────────────────────
  const fetchPending = useCallback(async () => {
    try {
      setError(null)
      const data = await apiClient.get<WorkbenchItem[]>('/api/workbench/pending')
      setItems(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pending items')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPending()
  }, [fetchPending])

  // ── Show toast ───────────────────────────────────────────────────────────
  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3500)
  }

  // ── Approve / Reject ─────────────────────────────────────────────────────
  const handleAction = async (id: number, action: 'approve' | 'reject') => {
    setActionLoading(true)
    try {
      await apiClient.post(`/api/workbench/${id}/${action}`, {})
      // Optimistic removal from list
      setItems((prev) => prev.filter((i) => i.id !== id))
      showToast(
        action === 'approve' ? '✅ Item approved successfully' : '❌ Item rejected',
        'success'
      )
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Action failed', 'error')
    } finally {
      setActionLoading(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8">
      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            key="toast"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className={cn(
              'fixed right-6 top-6 z-50 rounded-lg px-4 py-3 text-sm font-medium shadow-lg',
              toast.type === 'success'
                ? 'bg-emerald-600 text-white'
                : 'bg-red-600 text-white'
            )}
          >
            {toast.message}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Page header */}
      <motion.div variants={itemVariants} initial="hidden" animate="visible">
        <h1 className="text-display-3 font-bold tracking-tight text-brand-navy">
          AI Workbench
        </h1>
        <p className="mt-2 text-lg text-muted-foreground">
          Human-in-the-loop exception queue — review and resolve AI-escalated tickets.
        </p>
      </motion.div>

      {/* Pending queue */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-brand-navy">
            <Icons.alertCircle className="h-5 w-5 text-amber-500" />
            Pending Approval
            {!loading && (
              <span className="ml-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-700">
                {items.length}
              </span>
            )}
          </h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setLoading(true); fetchPending() }}
            disabled={loading}
          >
            <Icons.refresh className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div className="space-y-4">
            {[1, 2].map((i) => (
              <Card key={i} className="animate-pulse">
                <CardContent className="h-48 p-6">
                  <div className="space-y-3">
                    <div className="h-4 w-1/4 rounded bg-muted" />
                    <div className="h-4 w-3/4 rounded bg-muted" />
                    <div className="h-16 rounded bg-muted" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="flex items-center gap-3 p-6 text-red-700">
              <Icons.alertCircle className="h-5 w-5 flex-shrink-0" />
              <div>
                <p className="font-semibold">Failed to load queue</p>
                <p className="text-sm">{error}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Empty state */}
        {!loading && !error && items.length === 0 && (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center text-muted-foreground">
              <Icons.check className="h-10 w-10 text-emerald-400" />
              <p className="font-semibold">All clear!</p>
              <p className="text-sm">No items pending human review right now.</p>
            </CardContent>
          </Card>
        )}

        {/* Ticket cards */}
        <AnimatePresence mode="popLayout">
          {items.map((item) => (
            <TicketCard
              key={item.id}
              item={item}
              loading={actionLoading}
              onApprove={(id) => handleAction(id, 'approve')}
              onReject={(id) => handleAction(id, 'reject')}
            />
          ))}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
