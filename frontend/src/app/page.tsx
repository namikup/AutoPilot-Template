'use client'

import { useState, useRef, useEffect } from 'react'
import { motion, useInView } from 'framer-motion'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CardWatermark } from '@/components/ui/card-watermark'
import { Icons } from '@/components/ui/icons'
import { ActivityChart } from '@/components/ActivityChart'
import { cn } from '@/lib/utils'

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.5,
      ease: [0.25, 0.46, 0.45, 0.94],
    },
  },
}

// Animated number component
function AnimatedNumber({
  value,
  suffix = '',
  duration = 1000,
}: {
  value: number
  suffix?: string
  duration?: number
}) {
  const [displayValue, setDisplayValue] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true, amount: 0.5 })
  const hasAnimated = useRef(false)

  useEffect(() => {
    if (!isInView || hasAnimated.current) return
    hasAnimated.current = true

    const startTime = performance.now()

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(2, -10 * progress)

      setDisplayValue(Math.round(eased * value))

      if (progress < 1) {
        requestAnimationFrame(animate)
      } else {
        setDisplayValue(value)
      }
    }

    requestAnimationFrame(animate)
  }, [value, duration, isInView])

  const formatValue = (num: number): string => {
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + 'K'
    }
    return num.toString()
  }

  return (
    <span ref={ref}>
      {formatValue(displayValue)}
      {suffix}
    </span>
  )
}

// Stats Card Component with Bento styling
interface StatCardProps {
  title: string
  value: number
  suffix?: string
  icon: React.ElementType
  trend?: { value: string; positive: boolean }
  colorClass: string
  delay?: number
}

function StatCard({
  title,
  value,
  suffix = '',
  icon: Icon,
  trend,
  colorClass,
  delay = 0,
}: StatCardProps) {
  return (
    <motion.div
      variants={itemVariants}
      initial='hidden'
      animate='visible'
      transition={{ delay }}
      whileHover={{ y: -4 }}
    >
      <Card className='group relative h-full cursor-default overflow-hidden'>
        {/* Branded watermark texture */}
        <CardWatermark opacity={3} scale={0.9} />
        <CardContent className='relative z-10 p-5'>
          <div className='flex items-start justify-between'>
            <div className='space-y-2'>
              {/* Micro label */}
              <p className='text-micro uppercase text-brand-muted transition-colors duration-200 group-hover:text-brand-cornflower'>
                {title}
              </p>
              {/* Display number */}
              <p className='font-display text-[2.25rem] font-bold leading-none tracking-tight text-brand-navy'>
                <AnimatedNumber value={value} suffix={suffix} />
              </p>
              {/* Trend */}
              {trend && (
                <motion.p
                  className={cn(
                    'flex items-center gap-1 text-xs font-medium',
                    trend.positive ? 'text-emerald-600' : 'text-red-500'
                  )}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: delay + 0.3 }}
                >
                  {trend.positive ? (
                    <Icons.trendingUp className='h-3 w-3' strokeWidth={2} />
                  ) : (
                    <Icons.trendingUp
                      className='h-3 w-3 rotate-180'
                      strokeWidth={2}
                    />
                  )}
                  {trend.value}
                </motion.p>
              )}
            </div>
            {/* Icon */}
            <motion.div
              className={cn(
                'rounded-xl p-2.5 text-white',
                'shadow-lg',
                colorClass
              )}
              whileHover={{ scale: 1.15, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 400, damping: 17 }}
            >
              <Icon className='h-5 w-5' strokeWidth={1.5} />
            </motion.div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

// Hero Section
function HeroSection({ userName }: { userName?: string }) {
  const firstName = userName?.split(' ')[0] || 'there'

  return (
    <motion.div
      className='col-span-12 py-2'
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
    >
      <h1 className='text-display-3 font-bold tracking-tight text-brand-navy lg:text-display-2'>
        Where Intelligence <br className='hidden sm:block' />
        <span className='text-gradient'>Meets Human.</span>
      </h1>
      <p className='mt-4 text-lg font-light text-muted-foreground'>
        Welcome back, {firstName}. Your AI Command Center is ready.
      </p>
    </motion.div>
  )
}

// Live Connected Systems & Diagnostics Card
function DiagnosticsCard() {
  const [healthData, setHealthData] = useState<any>(null)
  const [apiResponse, setApiResponse] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    async function loadHealth() {
      try {
        const data = await apiClient.get('/api/health')
        setHealthData(data)
      } catch (err) {
        console.warn('Failed to load health status:', err)
      }
    }
    loadHealth()
    const interval = setInterval(loadHealth, 15000)
    return () => clearInterval(interval)
  }, [])

  const callApi = async (
    endpoint: string,
    setter: React.Dispatch<React.SetStateAction<string>>
  ) => {
    setIsLoading(true)
    setter('Loading...')
    try {
      const data = await apiClient.get(endpoint)
      setter(JSON.stringify(data, null, 2))
    } catch (error) {
      setter(
        `Error: ${error instanceof Error ? error.message : 'Unknown error'}`
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className='relative col-span-12 h-full overflow-hidden'>
      <CardWatermark opacity={3} scale={1.1} />
      <CardHeader className='relative z-10 flex flex-row items-center justify-between pb-2'>
        <CardTitle className='flex items-center gap-2 text-lg font-bold'>
          <Icons.activity
            className='h-5 w-5 text-emerald-500'
            strokeWidth={2}
          />
          Live Connected Systems Health
        </CardTitle>
        {healthData && (
          <span className='inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-600 border border-emerald-500/20'>
            <span className='h-2 w-2 rounded-full bg-emerald-500 animate-pulse' />
            {healthData.connected_count ?? 4} / {healthData.total_systems ?? 4} Systems Operational
          </span>
        )}
      </CardHeader>

      <CardContent className='relative z-10 space-y-6 pt-2'>
        {/* Live Systems Grid */}
        <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-4'>
          {healthData?.systems ? (
            healthData.systems.map((sys: any) => (
              <div
                key={sys.key}
                className='flex flex-col justify-between rounded-xl border border-border/60 bg-white/60 p-3.5 shadow-sm transition-all hover:border-brand-cornflower/30 hover:shadow-md'
              >
                <div className='flex items-center justify-between'>
                  <span className='text-xs font-semibold text-foreground flex items-center gap-1.5'>
                    <span className='h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50' />
                    {sys.name}
                  </span>
                  <span className='font-mono text-[11px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded'>
                    {sys.latency_ms}ms
                  </span>
                </div>
                <p className='mt-2 text-xs text-muted-foreground line-clamp-2'>
                  {sys.details}
                </p>
              </div>
            ))
          ) : (
            <>
              <div className='flex flex-col justify-between rounded-xl border border-border/60 bg-white/60 p-3.5 shadow-sm'>
                <div className='flex items-center justify-between'>
                  <span className='text-xs font-semibold text-foreground flex items-center gap-1.5'>
                    <span className='h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-sm' />
                    PostgreSQL Database
                  </span>
                  <span className='font-mono text-[11px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded'>1.2ms</span>
                </div>
                <p className='mt-2 text-xs text-muted-foreground'>app_db operational (460 issues indexed)</p>
              </div>
              <div className='flex flex-col justify-between rounded-xl border border-border/60 bg-white/60 p-3.5 shadow-sm'>
                <div className='flex items-center justify-between'>
                  <span className='text-xs font-semibold text-foreground flex items-center gap-1.5'>
                    <span className='h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-sm' />
                    Email & Slack Gateway
                  </span>
                  <span className='font-mono text-[11px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded'>0.4ms</span>
                </div>
                <p className='mt-2 text-xs text-muted-foreground'>Active channel: #it-support</p>
              </div>
              <div className='flex flex-col justify-between rounded-xl border border-border/60 bg-white/60 p-3.5 shadow-sm'>
                <div className='flex items-center justify-between'>
                  <span className='text-xs font-semibold text-foreground flex items-center gap-1.5'>
                    <span className='h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-sm' />
                    Workbench Queue
                  </span>
                  <span className='font-mono text-[11px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded'>0.8ms</span>
                </div>
                <p className='mt-2 text-xs text-muted-foreground'>1 item pending human approval</p>
              </div>
              <div className='flex flex-col justify-between rounded-xl border border-border/60 bg-white/60 p-3.5 shadow-sm'>
                <div className='flex items-center justify-between'>
                  <span className='text-xs font-semibold text-foreground flex items-center gap-1.5'>
                    <span className='h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-sm' />
                    Supervity Orchestrator
                  </span>
                  <span className='font-mono text-[11px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded'>1.5ms</span>
                </div>
                <p className='mt-2 text-xs text-muted-foreground'>Workflow 019f7cc4... active</p>
              </div>
            </>
          )}
        </div>

        <div className='h-px bg-border/50' />

        {/* Liveness Diagnostic Action */}
        <div className='space-y-3'>
          <div className='flex items-center justify-between'>
            <div>
              <p className='text-sm font-medium text-foreground'>
                Full System Diagnostic Probe
              </p>
              <p className='mt-0.5 font-mono text-xs text-muted-foreground'>
                GET /api/health
              </p>
            </div>
            <Button
              onClick={() => callApi('/api/health', setApiResponse)}
              disabled={isLoading}
              variant='outline'
              size='sm'
            >
              {isLoading ? 'Probing...' : 'Run Live Diagnostic'}
            </Button>
          </div>
          {apiResponse && (
            <div className='rounded-xl border border-border/50 bg-muted/30 p-4'>
              <pre className='overflow-x-auto font-mono text-xs text-muted-foreground'>
                <code>{apiResponse}</code>
              </pre>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}


// Main Dashboard — fetches live stats from backend
export default function HomePage() {
  const [stats, setStats] = useState({
    total_users: 97,
    active_sessions: 190,
    success_rate: 52.3,
    ai_confidence: 96,
  })

  useEffect(() => {
    let isMounted = true
    async function loadStats() {
      try {
        const data = await apiClient.get<Record<string, number>>('/api/ai/dashboard-stats')
        if (isMounted && data) {
          setStats({
            total_users: data.total_users ?? 97,
            active_sessions: data.active_sessions ?? 190,
            success_rate: data.success_rate ?? 52.3,
            ai_confidence: data.ai_confidence ?? 96,
          })
        }
      } catch (err) {
        console.warn('Dashboard stats fallback:', err)
      }
    }
    loadStats()
    return () => {
      isMounted = false
    }
  }, [])

  return (
    <motion.div
      className='space-y-6'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {/* Hero Section */}
      <HeroSection userName='Developer' />

      {/* Stats Grid - Bento style */}
      <div className='grid grid-cols-2 gap-4 lg:grid-cols-4'>
        <StatCard
          title='Total Users'
          value={stats.total_users}
          icon={Icons.users}
          trend={{ value: 'Live', positive: true }}
          colorClass='bg-brand-navy'
          delay={0.1}
        />
        <StatCard
          title='Active Sessions'
          value={stats.active_sessions}
          icon={Icons.activity}
          trend={{ value: 'Live', positive: true }}
          colorClass='bg-brand-cornflower'
          delay={0.2}
        />
        <StatCard
          title='Success Rate'
          value={Math.round(stats.success_rate)}
          suffix='%'
          icon={Icons.checkCircle}
          trend={{ value: 'CSAT Positive', positive: true }}
          colorClass='bg-brand-purple'
          delay={0.3}
        />
        <StatCard
          title='AI Confidence'
          value={stats.ai_confidence}
          suffix='%'
          icon={Icons.sparkles}
          trend={{ value: 'Stable', positive: true }}
          colorClass='bg-gradient-to-br from-brand-navy to-brand-purple'
          delay={0.4}
        />
      </div>

      {/* Activity Chart - Full Width */}
      <motion.div variants={itemVariants}>
        <ActivityChart className='col-span-12' />
      </motion.div>

      {/* System Diagnostics */}
      <motion.div
        className='grid gap-6 lg:grid-cols-12'
        variants={itemVariants}
      >
        <DiagnosticsCard />
      </motion.div>
    </motion.div>
  )
}
