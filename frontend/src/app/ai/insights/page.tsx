'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { apiClient } from '@/lib/api-client'

// ============================================================================
// Types — mirrors the backend response (app/schemas/insight.py: InsightOut)
// ============================================================================

export interface Insight {
  id: number
  insight_type: string | null
  title: string
  summary: string
  severity: 'critical' | 'high' | 'medium' | 'low' | null
  confidence: number | null
  evidence: Record<string, unknown> | null
  action_label: string | null
  action_type: string | null
  action_payload: Record<string, unknown> | null
  status: string
  computed_at: string
  computed_from: string | null
}

// ============================================================================
// Severity styling — red critical, amber high, blue medium, gray low
// ============================================================================

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high: 'bg-amber-100 text-amber-700 border-amber-200',
  medium: 'bg-blue-100 text-blue-700 border-blue-200',
  low: 'bg-gray-100 text-gray-600 border-gray-200',
}

const SEVERITY_ICON_BG: Record<string, string> = {
  critical: 'bg-red-100',
  high: 'bg-amber-100',
  medium: 'bg-blue-100',
  low: 'bg-gray-100',
}

const SEVERITY_ICON_COLOR: Record<string, string> = {
  critical: 'text-red-600',
  high: 'text-amber-600',
  medium: 'text-blue-600',
  low: 'text-gray-500',
}

// ============================================================================
// Animation Variants
// ============================================================================

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

// ============================================================================
// Helpers
// ============================================================================

const formatDateTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

// ============================================================================
// Page Component
// ============================================================================

export default function AIInsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isRecomputing, setIsRecomputing] = useState(false)
  const [actingId, setActingId] = useState<number | null>(null)
  const [dismissingId, setDismissingId] = useState<number | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  // ============================================================================
  // Data — loaded from the real backend
  // ============================================================================

  const fetchInsights = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await apiClient.get<Insight[]>('/api/insights')
      setInsights(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchInsights()
  }, [fetchInsights])

  // ============================================================================
  // Actions
  // ============================================================================

  const handleRecompute = useCallback(async () => {
    setIsRecomputing(true)
    setError(null)
    try {
      await apiClient.post('/api/insights/compute')
      await fetchInsights()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to recompute insights.')
    } finally {
      setIsRecomputing(false)
    }
  }, [fetchInsights])

  const handleAct = useCallback(
    async (id: number) => {
      setActingId(id)
      try {
        await apiClient.post(`/api/insights/${id}/act`)
        await fetchInsights()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to act on insight.')
      } finally {
        setActingId(null)
      }
    },
    [fetchInsights]
  )

  const handleDismiss = useCallback(
    async (id: number) => {
      setDismissingId(id)
      try {
        await apiClient.post(`/api/insights/${id}/dismiss`)
        await fetchInsights()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to dismiss insight.')
      } finally {
        setDismissingId(null)
      }
    },
    [fetchInsights]
  )

  const toggleExpanded = useCallback((id: number) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }, [])

  // ============================================================================
  // Stats
  // ============================================================================

  const stats = {
    critical: insights.filter((i) => i.severity === 'critical').length,
    high: insights.filter((i) => i.severity === 'high').length,
    open: insights.filter((i) => i.status === 'open').length,
  }

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <motion.div
      className="space-y-6"
      variants={containerVariants}
      initial="hidden"
      animate="visible"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="flex items-center justify-between">
        <div>
          <h1 className="text-display-3 font-bold tracking-tight text-brand-navy lg:text-display-2">
            AI Insights
          </h1>
          <p className="mt-2 text-lg text-muted-foreground">
            AI-generated observations computed from your operational data.
          </p>
        </div>
        <Button variant="gradient" onClick={handleRecompute} disabled={isRecomputing}>
          {isRecomputing ? (
            <>
              <Icons.loader className="mr-2 h-4 w-4 animate-spin" />
              Recomputing...
            </>
          ) : (
            <>
              <Icons.sparkles className="mr-2 h-4 w-4" strokeWidth={1.5} />
              Recompute insights
            </>
          )}
        </Button>
      </motion.div>

      {/* Stats Cards */}
      <motion.div variants={itemVariants} className="grid gap-4 sm:grid-cols-3">
        <Card className="relative overflow-hidden">
          <CardWatermark opacity={2} scale={0.8} />
          <CardContent className="relative z-10 flex items-center gap-4 py-6">
            <div className={cn('flex h-12 w-12 items-center justify-center rounded-xl', SEVERITY_ICON_BG.critical)}>
              <Icons.alertCircle className={cn('h-6 w-6', SEVERITY_ICON_COLOR.critical)} strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-2xl font-bold text-brand-navy">{stats.critical}</p>
              <p className="text-sm text-muted-foreground">Critical</p>
            </div>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardWatermark opacity={2} scale={0.8} />
          <CardContent className="relative z-10 flex items-center gap-4 py-6">
            <div className={cn('flex h-12 w-12 items-center justify-center rounded-xl', SEVERITY_ICON_BG.high)}>
              <Icons.alertTriangle className={cn('h-6 w-6', SEVERITY_ICON_COLOR.high)} strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-2xl font-bold text-brand-navy">{stats.high}</p>
              <p className="text-sm text-muted-foreground">High</p>
            </div>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardWatermark opacity={2} scale={0.8} />
          <CardContent className="relative z-10 flex items-center gap-4 py-6">
            <div className={cn('flex h-12 w-12 items-center justify-center rounded-xl', SEVERITY_ICON_BG.medium)}>
              <Icons.lightbulb className={cn('h-6 w-6', SEVERITY_ICON_COLOR.medium)} strokeWidth={1.5} />
            </div>
            <div>
              <p className="text-2xl font-bold text-brand-navy">{stats.open}</p>
              <p className="text-sm text-muted-foreground">Open</p>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Insights List */}
      <motion.div variants={itemVariants}>
        <Card className="relative overflow-hidden">
          <CardWatermark opacity={2} scale={1} />
          <CardHeader className="relative z-10">
            <CardTitle>All Insights</CardTitle>
            <CardDescription>
              {insights.length} insight{insights.length === 1 ? '' : 's'} computed from issues, policy evaluations, and workbench outcomes.
            </CardDescription>
          </CardHeader>
          <CardContent className="relative z-10 space-y-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Icons.loader className="h-8 w-8 animate-spin text-brand-cornflower" />
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100">
                  <Icons.alertTriangle className="h-8 w-8 text-red-600" strokeWidth={1.5} />
                </div>
                <h3 className="font-display text-lg font-semibold text-brand-navy">
                  Couldn&apos;t load insights
                </h3>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">{error}</p>
                <Button variant="outline" className="mt-6" onClick={() => fetchInsights()}>
                  <Icons.refresh className="mr-2 h-4 w-4" />
                  Try Again
                </Button>
              </div>
            ) : insights.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className={cn(
                  'mb-4 flex h-16 w-16 items-center justify-center rounded-2xl',
                  'bg-gradient-to-br from-brand-cornflower/20 to-brand-purple/20'
                )}>
                  <Icons.lightbulb className="h-8 w-8 text-brand-cornflower" strokeWidth={1.5} />
                </div>
                <h3 className="font-display text-lg font-semibold text-brand-navy">
                  No insights yet
                </h3>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Recompute insights to discover patterns, anomalies, and optimization opportunities.
                </p>
                <Button variant="gradient" className="mt-6" onClick={handleRecompute} disabled={isRecomputing}>
                  <Icons.sparkles className="mr-2 h-4 w-4" strokeWidth={1.5} />
                  Recompute insights
                </Button>
              </div>
            ) : (
              insights.map((insight) => {
                const severityKey = insight.severity ?? 'low'
                const isExpanded = expandedId === insight.id
                const isOpen = insight.status === 'open'
                const hasAction = isOpen && !!insight.action_type && insight.action_type !== 'none'

                return (
                  <motion.div
                    key={insight.id}
                    layout
                    className={cn(
                      'rounded-xl border p-4 transition-all duration-200 hover:shadow-soft',
                      'bg-white',
                      !isOpen && 'opacity-70'
                    )}
                  >
                    <div className="flex gap-4">
                      <div className={cn(
                        'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg',
                        SEVERITY_ICON_BG[severityKey] ?? SEVERITY_ICON_BG.low
                      )}>
                        <Icons.alertTriangle
                          className={cn('h-5 w-5', SEVERITY_ICON_COLOR[severityKey] ?? SEVERITY_ICON_COLOR.low)}
                          strokeWidth={1.5}
                        />
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="font-semibold text-foreground">{insight.title}</h4>
                          <span className={cn(
                            'rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase',
                            SEVERITY_STYLES[severityKey] ?? SEVERITY_STYLES.low
                          )}>
                            {insight.severity ?? 'unknown'}
                          </span>
                          {!isOpen && (
                            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase text-muted-foreground">
                              {insight.status}
                            </span>
                          )}
                        </div>

                        <p className="mt-2 text-sm text-muted-foreground">{insight.summary}</p>

                        <p className="mt-2 text-xs text-muted-foreground">
                          {formatDateTime(insight.computed_at)}
                          {insight.computed_from && ` • ${insight.computed_from}`}
                        </p>

                        {/* Evidence — expandable, readable JSON */}
                        {insight.evidence && (
                          <div className="mt-3">
                            <button
                              onClick={() => toggleExpanded(insight.id)}
                              className="flex items-center gap-1 text-xs font-medium text-brand-cornflower hover:text-brand-navy transition-colors"
                            >
                              <Icons.chevronRight
                                className={cn('h-3.5 w-3.5 transition-transform duration-200', isExpanded && 'rotate-90')}
                              />
                              {isExpanded ? 'Hide evidence' : 'Show evidence'}
                            </button>
                            <AnimatePresence initial={false}>
                              {isExpanded && (
                                <motion.div
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: 'auto', opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  transition={{ duration: 0.2 }}
                                  className="overflow-hidden"
                                >
                                  <pre className="mt-2 max-h-64 overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs font-mono text-gray-700">
                                    {JSON.stringify(insight.evidence, null, 2)}
                                  </pre>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="mt-4 flex items-center gap-2">
                          {hasAction && (
                            <Button
                              variant="default"
                              size="sm"
                              disabled={actingId === insight.id}
                              onClick={() => handleAct(insight.id)}
                            >
                              {actingId === insight.id ? (
                                <Icons.loader className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Icons.zap className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.5} />
                              )}
                              {insight.action_label ?? 'Act'}
                            </Button>
                          )}
                          {isOpen && (
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={dismissingId === insight.id}
                              onClick={() => handleDismiss(insight.id)}
                              className="text-muted-foreground hover:text-foreground"
                            >
                              {dismissingId === insight.id ? (
                                <Icons.loader className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Icons.close className="mr-1.5 h-3.5 w-3.5" />
                              )}
                              Dismiss
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )
              })
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  )
}
