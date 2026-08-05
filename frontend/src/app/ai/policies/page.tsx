'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { apiClient } from '@/lib/api-client'
import { PermissionMatrixTab } from '@/components/ai/policies/PermissionMatrixTab'

// ============================================================================
// Types — mirrors the backend response (app/schemas/policy.py: PolicyOut)
// ============================================================================

export interface Policy {
  id: string
  name: string
  description: string | null
  category: string
  enabled: boolean
  priority: number
  params: Record<string, unknown>
  version: number
  updated_by: string | null
  updated_at: string
}

// ============================================================================
// Animation Variants
// ============================================================================

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

// ============================================================================
// Types
// ============================================================================

type TabType = 'policies' | 'matrix'
type FilterType = 'all' | 'enabled' | 'disabled'
type SortType = 'priority' | 'name' | 'version' | 'updated'

// ============================================================================
// Tab Configuration
// ============================================================================

const TABS = [
  { id: 'policies' as TabType, label: 'Policies', Icon: Icons.layers },
  { id: 'matrix' as TabType, label: 'Permission Matrix', Icon: Icons.table },
]

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

export default function AIPoliciesPage() {
  // State
  const [policies, setPolicies] = useState<Policy[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabType>('policies')

  // Filters
  const [filter, setFilter] = useState<FilterType>('all')
  const [sortBy, setSortBy] = useState<SortType>('priority')
  const [searchQuery, setSearchQuery] = useState('')

  // ============================================================================
  // Data — loaded from the real backend
  // ============================================================================

  const fetchPolicies = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await apiClient.get<Policy[]>('/api/policies')
      setPolicies(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load policies.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPolicies()
  }, [fetchPolicies])

  // ============================================================================
  // Policy Actions
  // ============================================================================

  const toggleEnabled = useCallback(
    async (id: string, currentEnabled: boolean) => {
      setTogglingId(id)
      try {
        await apiClient.patch(`/api/policies/${id}`, { enabled: !currentEnabled })
        await fetchPolicies()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update policy.')
      } finally {
        setTogglingId(null)
      }
    },
    [fetchPolicies]
  )

  // ============================================================================
  // Filtering & Sorting
  // ============================================================================

  const categories = Array.from(new Set(policies.map((p) => p.category))).sort()

  const filteredPolicies = policies
    .filter((policy) => {
      if (filter === 'enabled' && !policy.enabled) return false
      if (filter === 'disabled' && policy.enabled) return false

      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          policy.name.toLowerCase().includes(query) ||
          policy.id.toLowerCase().includes(query) ||
          (policy.description ?? '').toLowerCase().includes(query) ||
          policy.category.toLowerCase().includes(query)
        )
      }

      return true
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'priority':
          return a.priority - b.priority
        case 'name':
          return a.name.localeCompare(b.name)
        case 'version':
          return b.version - a.version
        case 'updated':
          return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        default:
          return 0
      }
    })

  // ============================================================================
  // Stats
  // ============================================================================

  const stats = {
    total: policies.length,
    enabled: policies.filter((p) => p.enabled).length,
    disabled: policies.filter((p) => !p.enabled).length,
    categories: categories.length,
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
      <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-display-3 font-bold tracking-tight text-brand-navy lg:text-display-2">
            AI Policies
          </h1>
          <p className="mt-1 text-lg text-muted-foreground">
            Governance rules that constrain AI agent behavior. Seeded server-side — toggle them on or off here.
          </p>
        </div>
      </motion.div>

      {/* Tabs - AT THE TOP */}
      <motion.div variants={itemVariants}>
        <div className="flex gap-1 p-1.5 bg-gray-100 rounded-xl w-fit">
          {TABS.map((tab) => (
            <motion.button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'relative flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors',
                activeTab === tab.id
                  ? 'text-brand-navy'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              whileHover={{ scale: activeTab === tab.id ? 1 : 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {activeTab === tab.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 bg-white rounded-lg shadow-sm"
                  transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                />
              )}
              <span className="relative z-10 flex items-center gap-2">
                <tab.Icon className="h-4 w-4" />
                {tab.label}
              </span>
            </motion.button>
          ))}
        </div>
      </motion.div>

      {/* Tab Content - Use initial={false} on first render to avoid blank state */}
      <AnimatePresence mode="popLayout">
        {activeTab === 'policies' && (
          <motion.div
            key="policies-tab"
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.15 }}
            className="space-y-6"
          >
          {/* Stats Bar - No initial animation to prevent blank flash */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { value: stats.total, label: 'Total Policies', icon: Icons.layers, bg: 'bg-brand-navy/10', color: 'text-brand-navy' },
              { value: stats.enabled, label: 'Enabled', icon: Icons.check, bg: 'bg-emerald-100', color: 'text-emerald-600' },
              { value: stats.disabled, label: 'Disabled', icon: Icons.eyeOff, bg: 'bg-gray-100', color: 'text-gray-600' },
              { value: stats.categories, label: 'Categories', icon: Icons.grid, bg: 'bg-blue-100', color: 'text-blue-600' },
            ].map((stat) => (
              <motion.div
                key={stat.label}
                className="bg-white rounded-xl border border-gray-200 p-4 hover:border-gray-300 hover:shadow-md transition-all cursor-default"
                whileHover={{ y: -2, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              >
                <div className="flex items-center gap-3">
                  <motion.div
                    className={cn('p-2 rounded-lg', stat.bg)}
                    whileHover={{ scale: 1.1, rotate: 5 }}
                    transition={{ type: 'spring', stiffness: 400 }}
                  >
                    <stat.icon className={cn('h-5 w-5', stat.color)} />
                  </motion.div>
                  <div>
                    <p className={cn('text-2xl font-bold', stat.color)}>
                      {stat.value}
                    </p>
                    <p className="text-xs text-muted-foreground">{stat.label}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Filters & Search */}
          <motion.div variants={itemVariants} className="flex flex-col sm:flex-row gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Icons.search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search policies..."
                className={cn(
                  'w-full pl-10 pr-4 py-2.5 rounded-lg border border-input bg-white',
                  'text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50'
                )}
              />
            </div>

            {/* Filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">Filter:</span>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as FilterType)}
                className="px-3 py-2.5 rounded-lg border border-input bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
              >
                <option value="all">All</option>
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
            </div>

            {/* Sort */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground whitespace-nowrap">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as SortType)}
                className="px-3 py-2.5 rounded-lg border border-input bg-white text-sm focus:outline-none focus:ring-2 focus:ring-brand-cornflower/50"
              >
                <option value="priority">Priority</option>
                <option value="name">Name</option>
                <option value="version">Version</option>
                <option value="updated">Last Updated</option>
              </select>
            </div>
          </motion.div>

          {/* Policy Grid */}
          <motion.div variants={itemVariants}>
            {isLoading ? (
              <div className="flex items-center justify-center py-16">
                <Icons.loader className="h-8 w-8 animate-spin text-brand-cornflower" />
              </div>
            ) : error ? (
              <Card className="relative overflow-hidden border-red-200">
                <CardContent className="relative z-10 flex flex-col items-center justify-center py-16 text-center">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100">
                    <Icons.alertTriangle className="h-8 w-8 text-red-600" strokeWidth={1.5} />
                  </div>
                  <h3 className="font-display text-lg font-semibold text-brand-navy">
                    Couldn&apos;t load policies
                  </h3>
                  <p className="mt-1 max-w-sm text-sm text-muted-foreground">{error}</p>
                  <Button variant="outline" className="mt-6" onClick={() => fetchPolicies()}>
                    <Icons.refresh className="mr-2 h-4 w-4" />
                    Try Again
                  </Button>
                </CardContent>
              </Card>
            ) : filteredPolicies.length === 0 ? (
              <Card className="relative overflow-hidden">
                <CardWatermark opacity={3} scale={1} />
                <CardContent className="relative z-10 flex flex-col items-center justify-center py-16 text-center">
                  <div className={cn(
                    'mb-4 flex h-16 w-16 items-center justify-center rounded-2xl',
                    'bg-gradient-to-br from-brand-cornflower/20 to-brand-purple/20'
                  )}>
                    <Icons.brain className="h-8 w-8 text-brand-cornflower" strokeWidth={1.5} />
                  </div>
                  <h3 className="font-display text-lg font-semibold text-brand-navy">
                    {searchQuery || filter !== 'all' ? 'No matching policies' : 'No policies yet'}
                  </h3>
                  <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                    {searchQuery || filter !== 'all'
                      ? 'Try adjusting your search or filter criteria.'
                      : 'Policies are seeded server-side — run the seed script to populate them.'}
                  </p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filteredPolicies.map((policy) => (
                  <motion.div
                    key={policy.id}
                    className={cn(
                      'relative rounded-xl border bg-white flex flex-col group',
                      !policy.enabled && 'opacity-60'
                    )}
                    whileHover={{
                      y: -4,
                      boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)',
                      borderColor: 'rgba(156, 163, 175, 0.5)',
                    }}
                    transition={{ type: 'spring', stiffness: 400, damping: 25 }}
                  >
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2 p-4 pb-2">
                      <div className="flex items-start gap-2 flex-1 min-w-0">
                        {/* Status Dot with pulse animation when enabled */}
                        <div className="relative mt-1.5 flex-shrink-0">
                          <div className={cn(
                            'h-2.5 w-2.5 rounded-full',
                            policy.enabled ? 'bg-emerald-500' : 'bg-gray-300'
                          )} />
                          {policy.enabled && (
                            <div className="absolute inset-0 h-2.5 w-2.5 rounded-full bg-emerald-500 animate-ping opacity-40" />
                          )}
                        </div>

                        <div className="min-w-0">
                          <h3 className="font-semibold text-brand-navy line-clamp-1 text-sm group-hover:text-brand-cornflower transition-colors duration-200">
                            {policy.name}
                          </h3>
                          <p className="text-[11px] font-mono text-muted-foreground truncate">
                            {policy.id}
                          </p>
                        </div>
                      </div>

                      {/* Category Badge */}
                      <span className="flex-shrink-0 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-blue-100 text-blue-700">
                        {policy.category}
                      </span>
                    </div>

                    {/* Description */}
                    <div className="px-4 pb-2 flex-1 min-h-0">
                      <p className="text-sm text-muted-foreground line-clamp-2">
                        {policy.description || 'No description provided.'}
                      </p>
                    </div>

                    {/* Priority / Version chips */}
                    <div className="px-4 pb-3 flex flex-wrap items-center gap-1.5">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-amber-50 text-amber-700 border border-amber-100">
                        <Icons.flag className="h-2.5 w-2.5" />
                        Priority {policy.priority}
                      </span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-gray-100 text-gray-600 border border-gray-200">
                        v{policy.version}
                      </span>
                    </div>

                    {/* Footer - Fixed at bottom */}
                    <div className="relative flex items-center justify-between gap-2 px-4 py-3 border-t border-gray-100 mt-auto bg-gray-50/50 rounded-b-xl">
                      <div className="min-w-0 text-xs text-muted-foreground">
                        <p className="truncate">
                          {policy.updated_by ? `By ${policy.updated_by}` : 'Not yet updated'}
                        </p>
                        <p className="truncate">{formatDateTime(policy.updated_at)}</p>
                      </div>

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={togglingId === policy.id}
                        onClick={() => toggleEnabled(policy.id, policy.enabled)}
                        className={cn(
                          'flex-shrink-0 transition-colors',
                          policy.enabled
                            ? 'text-amber-600 hover:text-amber-700 hover:bg-amber-50 hover:border-amber-200'
                            : 'text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 hover:border-emerald-200'
                        )}
                      >
                        {togglingId === policy.id ? (
                          <Icons.loader className="h-3.5 w-3.5 animate-spin" />
                        ) : policy.enabled ? (
                          <>
                            <Icons.eyeOff className="h-3.5 w-3.5 mr-1.5" />
                            Disable
                          </>
                        ) : (
                          <>
                            <Icons.eye className="h-3.5 w-3.5 mr-1.5" />
                            Enable
                          </>
                        )}
                      </Button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        </motion.div>
      )}

      {activeTab === 'matrix' && (
        <motion.div
          key="matrix-tab"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.15 }}
        >
          <PermissionMatrixTab />
        </motion.div>
      )}
      </AnimatePresence>
    </motion.div>
  )
}
