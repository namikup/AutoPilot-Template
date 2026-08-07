'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import { motion, AnimatePresence } from 'framer-motion'
import Link from 'next/link'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Avatar } from '@/components/ui/avatar'
import { Icons } from '@/components/ui/icons'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

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

interface ProfileData {
  name: string
  email: string
  department: string
  location: string
  title: string
}

interface QuickSettings {
  emailNotifications: boolean
  desktopNotifications: boolean
  weeklyDigest: boolean
  marketingEmails: boolean
  compactMode: boolean
  soundEffects: boolean
}

interface NotificationsConfig {
  quietHours: boolean
  quietStart: string
  quietEnd: string
  slackWebhook: string
  securityAlertsOnly: boolean
  digestFrequency: string
}

interface SecurityConfig {
  twoFactorEnabled: boolean
  sessions: Array<{ id: string; device: string; location: string; lastActive: string; current?: boolean }>
}

interface IntegrationsConfig {
  jira: { connected: boolean; token: string }
  slack: { connected: boolean; token: string }
  github: { connected: boolean; token: string }
  pagerduty: { connected: boolean; token: string }
}

interface PreferencesConfig {
  language: string
  timezone: string
  dateFormat: string
  theme: string
}

const DEFAULT_PROFILE: ProfileData = {
  name: 'Uma Ong',
  email: 'uma.ong@company.com',
  department: 'Ops',
  location: 'Singapore',
  title: 'AutoPilot AI Specialist',
}

const DEFAULT_QUICK_SETTINGS: QuickSettings = {
  emailNotifications: true,
  desktopNotifications: true,
  weeklyDigest: false,
  marketingEmails: false,
  compactMode: false,
  soundEffects: true,
}

const DEFAULT_NOTIFICATIONS: NotificationsConfig = {
  quietHours: true,
  quietStart: '22:00',
  quietEnd: '07:00',
  slackWebhook: 'https://hooks.slack.com/services/sample/token',
  securityAlertsOnly: false,
  digestFrequency: 'weekly',
}

const DEFAULT_SECURITY: SecurityConfig = {
  twoFactorEnabled: true,
  sessions: [
    { id: 's1', device: 'MacBook Air (macOS 15.0)', location: 'Singapore', lastActive: 'Active now', current: true },
    { id: 's2', device: 'iPhone 15 Pro (iOS 18)', location: 'KL-HQ, Malaysia', lastActive: '2 hours ago' },
    { id: 's3', device: 'Chrome on Linux Workstation', location: 'Penang, Malaysia', lastActive: '3 days ago' },
  ],
}

const DEFAULT_INTEGRATIONS: IntegrationsConfig = {
  jira: { connected: true, token: 'jsm_pat_839210481239' },
  slack: { connected: true, token: 'xoxb-9281048201-82019401' },
  github: { connected: true, token: 'ghp_4920184019284019284' },
  pagerduty: { connected: false, token: '' },
}

const DEFAULT_PREFERENCES: PreferencesConfig = {
  language: 'en',
  timezone: 'Asia/Kuala_Lumpur',
  dateFormat: 'YYYY-MM-DD',
  theme: 'system',
}

export default function SettingsPage() {
  const { data: session } = useSession()

  // State initialization with localStorage fallback
  const [profile, setProfile] = useState<ProfileData>(DEFAULT_PROFILE)
  const [quickSettings, setQuickSettings] = useState<QuickSettings>(DEFAULT_QUICK_SETTINGS)
  const [notificationsConfig, setNotificationsConfig] = useState<NotificationsConfig>(DEFAULT_NOTIFICATIONS)
  const [securityConfig, setSecurityConfig] = useState<SecurityConfig>(DEFAULT_SECURITY)
  const [integrationsConfig, setIntegrationsConfig] = useState<IntegrationsConfig>(DEFAULT_INTEGRATIONS)
  const [preferencesConfig, setPreferencesConfig] = useState<PreferencesConfig>(DEFAULT_PREFERENCES)

  // Toast / Feedback State
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null)

  // Modal Visibility Controls
  const [isEditProfileOpen, setIsEditProfileOpen] = useState(false)
  const [activeConfigModal, setActiveConfigModal] = useState<'notifications' | 'security' | 'integrations' | 'preferences' | null>(null)
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false)
  const [isDeleteAccountOpen, setIsDeleteAccountOpen] = useState(false)

  // Form states inside modals
  const [editProfileForm, setEditProfileForm] = useState<ProfileData>(DEFAULT_PROFILE)
  const [passwordForm, setPasswordForm] = useState({ current: '', new: '', confirm: '' })
  const [deleteConfirmText, setDeleteConfirmText] = useState('')

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const savedProfile = localStorage.getItem('autopilot_profile')
      if (savedProfile) {
        setProfile(JSON.parse(savedProfile))
      } else if (session?.user) {
        const user = session.user
        setProfile((prev) => ({
          ...prev,
          name: user.name || prev.name,
          email: user.email || prev.email,
        }))
      }

      const savedQuick = localStorage.getItem('autopilot_quick_settings')
      if (savedQuick) setQuickSettings(JSON.parse(savedQuick))

      const savedNotifs = localStorage.getItem('autopilot_notifs_config')
      if (savedNotifs) setNotificationsConfig(JSON.parse(savedNotifs))

      const savedSec = localStorage.getItem('autopilot_sec_config')
      if (savedSec) setSecurityConfig(JSON.parse(savedSec))

      const savedInteg = localStorage.getItem('autopilot_integ_config')
      if (savedInteg) setIntegrationsConfig(JSON.parse(savedInteg))

      const savedPref = localStorage.getItem('autopilot_pref_config')
      if (savedPref) setPreferencesConfig(JSON.parse(savedPref))
    } catch {
      // Ignore storage errors
    }
  }, [session])

  const showToast = (text: string, type: 'success' | 'info' | 'error' = 'success') => {
    setToastMessage({ type, text })
    setTimeout(() => setToastMessage(null), 4000)
  }

  // Handle Quick Setting Toggle
  const handleQuickToggle = (key: keyof QuickSettings, checked: boolean) => {
    const updated = { ...quickSettings, [key]: checked }
    setQuickSettings(updated)
    try {
      localStorage.setItem('autopilot_quick_settings', JSON.stringify(updated))
    } catch {}
    showToast(`Setting updated!`)
  }

  // Handle Profile Save
  const handleSaveProfile = () => {
    setProfile(editProfileForm)
    try {
      localStorage.setItem('autopilot_profile', JSON.stringify(editProfileForm))
      window.dispatchEvent(new Event('profile_updated'))
    } catch {}
    setIsEditProfileOpen(false)
    showToast('Profile updated successfully!')
  }

  // Handle Password Change
  const handleChangePassword = () => {
    if (!passwordForm.current) {
      showToast('Please enter your current password', 'error')
      return
    }
    if (passwordForm.new.length < 8) {
      showToast('New password must be at least 8 characters long', 'error')
      return
    }
    if (passwordForm.new !== passwordForm.confirm) {
      showToast('New passwords do not match', 'error')
      return
    }
    setPasswordForm({ current: '', new: '', confirm: '' })
    showToast('Password changed successfully!')
  }

  // Handle Revoke Session
  const handleRevokeSession = (sessionId: string) => {
    const updated = {
      ...securityConfig,
      sessions: securityConfig.sessions.filter((s) => s.id !== sessionId),
    }
    setSecurityConfig(updated)
    try {
      localStorage.setItem('autopilot_sec_config', JSON.stringify(updated))
    } catch {}
    showToast('Session revoked successfully')
  }

  // Handle Reset All Settings
  const handleResetAllSettings = () => {
    setQuickSettings(DEFAULT_QUICK_SETTINGS)
    setNotificationsConfig(DEFAULT_NOTIFICATIONS)
    setSecurityConfig(DEFAULT_SECURITY)
    setIntegrationsConfig(DEFAULT_INTEGRATIONS)
    setPreferencesConfig(DEFAULT_PREFERENCES)
    try {
      localStorage.clear()
    } catch {}
    setIsResetConfirmOpen(false)
    showToast('All settings reset to default values', 'info')
  }

  // Handle Account Deletion
  const handleDeleteAccount = () => {
    if (deleteConfirmText !== 'DELETE') {
      showToast('Please type DELETE to confirm account deletion', 'error')
      return
    }
    setIsDeleteAccountOpen(false)
    setDeleteConfirmText('')
    showToast('Account deletion request initiated', 'info')
  }

  const isAdmin = session?.roles?.includes('admin') || true

  return (
    <motion.div
      className='space-y-8 pb-12'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {/* Toast Notification Banner */}
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className={`fixed top-4 right-4 z-50 flex items-center gap-3 rounded-xl p-4 shadow-lg border text-sm font-medium ${
              toastMessage.type === 'error'
                ? 'bg-red-50 text-red-800 border-red-200'
                : toastMessage.type === 'info'
                ? 'bg-blue-50 text-blue-800 border-blue-200'
                : 'bg-emerald-50 text-emerald-800 border-emerald-200'
            }`}
          >
            {toastMessage.type === 'error' ? (
              <Icons.alertCircle className='h-5 w-5 text-red-600' />
            ) : toastMessage.type === 'info' ? (
              <Icons.info className='h-5 w-5 text-blue-600' />
            ) : (
              <Icons.checkCircle className='h-5 w-5 text-emerald-600' />
            )}
            <span>{toastMessage.text}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <motion.div variants={itemVariants} className='flex items-center justify-between'>
        <div>
          <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
            Settings & Controls
          </h1>
          <p className='mt-1 text-base text-muted-foreground'>
            Manage profile, security parameters, system integrations, and preferences.
          </p>
        </div>
        <Button
          variant='outline'
          onClick={() => setIsResetConfirmOpen(true)}
          className='flex items-center gap-2 text-xs font-semibold text-gray-600 hover:text-brand-navy'
        >
          <Icons.refresh className='h-3.5 w-3.5' />
          Reset All Defaults
        </Button>
      </motion.div>

      {/* Profile Section */}
      <motion.div variants={itemVariants}>
        <Card className='relative overflow-hidden border-border/80 shadow-sm'>
          <CardHeader>
            <CardTitle className='text-lg font-bold text-brand-navy flex items-center gap-2'>
              <Icons.user className='h-5 w-5 text-brand-cornflower' />
              User Profile & Identity
            </CardTitle>
            <CardDescription>Your account details and organization metadata</CardDescription>
          </CardHeader>
          <CardContent>
            <div className='flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6'>
              <div className='flex items-center gap-5'>
                <Avatar
                  src={session?.user?.image}
                  fallback={profile.name || 'User'}
                  size='lg'
                  showRing
                />
                <div className='space-y-1'>
                  <div className='flex items-center gap-2.5'>
                    <h3 className='text-xl font-bold text-foreground'>{profile.name}</h3>
                    <span className='rounded-full bg-brand-cornflower/10 px-2.5 py-0.5 text-xs font-semibold text-brand-cornflower border border-brand-cornflower/20'>
                      {profile.title}
                    </span>
                  </div>
                  <p className='text-sm text-muted-foreground'>{profile.email}</p>
                  <div className='flex flex-wrap items-center gap-4 pt-1 text-xs text-muted-foreground'>
                    <span className='flex items-center gap-1.5'>
                      <Icons.building className='h-3.5 w-3.5 text-gray-400' />
                      Department: <strong className='text-foreground'>{profile.department}</strong>
                    </span>
                    <span className='flex items-center gap-1.5'>
                      <Icons.globe className='h-3.5 w-3.5 text-gray-400' />
                      Location: <strong className='text-foreground'>{profile.location}</strong>
                    </span>
                  </div>
                </div>
              </div>
              <Button
                variant='outline'
                onClick={() => {
                  setEditProfileForm(profile)
                  setIsEditProfileOpen(true)
                }}
                className='flex items-center gap-2 border-brand-cornflower/30 text-brand-cornflower hover:bg-brand-cornflower/10'
              >
                <Icons.edit className='h-4 w-4' />
                Edit Profile
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Admin System Settings Banner (If Admin) */}
      {isAdmin && (
        <motion.div variants={itemVariants}>
          <Card className='border-emerald-200 bg-gradient-to-r from-emerald-50/60 to-teal-50/40 shadow-sm'>
            <CardContent className='flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 gap-4'>
              <div className='flex items-center gap-3.5'>
                <div className='flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-sm'>
                  <Icons.shield className='h-5 w-5' />
                </div>
                <div>
                  <h4 className='text-sm font-bold text-emerald-950'>System Admin Settings</h4>
                  <p className='text-xs text-emerald-800/80'>
                    Configure company-wide approved domains, Keycloak access policies, and system settings.
                  </p>
                </div>
              </div>
              <Link href='/admin/settings'>
                <Button size='sm' className='bg-emerald-600 hover:bg-emerald-700 text-white gap-2'>
                  Configure Admin Settings
                  <Icons.arrowRight className='h-3.5 w-3.5' />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Settings Cards Grid */}
      <div className='grid gap-6 md:grid-cols-2'>
        {/* Notifications Card */}
        <motion.div variants={itemVariants}>
          <Card className='h-full flex flex-col justify-between hover:border-brand-cornflower/40 transition-all shadow-sm'>
            <CardHeader>
              <div className='flex items-center gap-3'>
                <div className='flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-600'>
                  <Icons.bell className='h-5 w-5' strokeWidth={1.8} />
                </div>
                <div>
                  <CardTitle className='text-base font-bold text-brand-navy'>Notifications</CardTitle>
                  <CardDescription className='text-xs'>
                    Quiet hours, webhook alerts, and digest delivery
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='space-y-2 text-xs text-muted-foreground bg-gray-50/80 p-3 rounded-lg border border-gray-100'>
                <div className='flex justify-between'>
                  <span>Quiet Hours:</span>
                  <span className='font-semibold text-foreground'>
                    {notificationsConfig.quietHours ? `${notificationsConfig.quietStart} - ${notificationsConfig.quietEnd}` : 'Disabled'}
                  </span>
                </div>
                <div className='flex justify-between'>
                  <span>Digest Frequency:</span>
                  <span className='font-semibold text-foreground capitalize'>{notificationsConfig.digestFrequency}</span>
                </div>
              </div>
              <Button
                variant='outline'
                onClick={() => setActiveConfigModal('notifications')}
                className='w-full justify-between hover:bg-brand-cornflower/5 text-sm font-medium'
              >
                Configure Notification Preferences
                <Icons.chevronRight className='h-4 w-4 text-muted-foreground' />
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* Security Card */}
        <motion.div variants={itemVariants}>
          <Card className='h-full flex flex-col justify-between hover:border-brand-cornflower/40 transition-all shadow-sm'>
            <CardHeader>
              <div className='flex items-center gap-3'>
                <div className='flex h-11 w-11 items-center justify-center rounded-xl bg-purple-50 text-purple-600'>
                  <Icons.eye className='h-5 w-5' strokeWidth={1.8} />
                </div>
                <div>
                  <CardTitle className='text-base font-bold text-brand-navy'>Security & Auth</CardTitle>
                  <CardDescription className='text-xs'>
                    Password update, 2FA status, and session devices
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='space-y-2 text-xs text-muted-foreground bg-gray-50/80 p-3 rounded-lg border border-gray-100'>
                <div className='flex justify-between'>
                  <span>Two-Factor Auth:</span>
                  <span className={`font-semibold ${securityConfig.twoFactorEnabled ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {securityConfig.twoFactorEnabled ? 'Enabled (Active)' : 'Disabled'}
                  </span>
                </div>
                <div className='flex justify-between'>
                  <span>Active Sessions:</span>
                  <span className='font-semibold text-foreground'>{securityConfig.sessions.length} devices linked</span>
                </div>
              </div>
              <Button
                variant='outline'
                onClick={() => setActiveConfigModal('security')}
                className='w-full justify-between hover:bg-brand-cornflower/5 text-sm font-medium'
              >
                Manage Password & Security
                <Icons.chevronRight className='h-4 w-4 text-muted-foreground' />
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* Integrations Card */}
        <motion.div variants={itemVariants}>
          <Card className='h-full flex flex-col justify-between hover:border-brand-cornflower/40 transition-all shadow-sm'>
            <CardHeader>
              <div className='flex items-center gap-3'>
                <div className='flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600'>
                  <Icons.share className='h-5 w-5' strokeWidth={1.8} />
                </div>
                <div>
                  <CardTitle className='text-base font-bold text-brand-navy'>Connected Integrations</CardTitle>
                  <CardDescription className='text-xs'>
                    API connections for Jira, Slack, GitHub, PagerDuty
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='flex flex-wrap gap-2'>
                {Object.entries(integrationsConfig).map(([key, item]) => (
                  <span
                    key={key}
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold capitalize border ${
                      item.connected
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-gray-100 text-gray-500 border-gray-200'
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${item.connected ? 'bg-emerald-500' : 'bg-gray-400'}`} />
                    {key}
                  </span>
                ))}
              </div>
              <Button
                variant='outline'
                onClick={() => setActiveConfigModal('integrations')}
                className='w-full justify-between hover:bg-brand-cornflower/5 text-sm font-medium'
              >
                Manage API Integrations
                <Icons.chevronRight className='h-4 w-4 text-muted-foreground' />
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* Preferences Card */}
        <motion.div variants={itemVariants}>
          <Card className='h-full flex flex-col justify-between hover:border-brand-cornflower/40 transition-all shadow-sm'>
            <CardHeader>
              <div className='flex items-center gap-3'>
                <div className='flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 text-amber-600'>
                  <Icons.settings className='h-5 w-5' strokeWidth={1.8} />
                </div>
                <div>
                  <CardTitle className='text-base font-bold text-brand-navy'>System Preferences</CardTitle>
                  <CardDescription className='text-xs'>
                    Language, timezone, and display formats
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='space-y-2 text-xs text-muted-foreground bg-gray-50/80 p-3 rounded-lg border border-gray-100'>
                <div className='flex justify-between'>
                  <span>Timezone:</span>
                  <span className='font-semibold text-foreground'>{preferencesConfig.timezone}</span>
                </div>
                <div className='flex justify-between'>
                  <span>Date Format:</span>
                  <span className='font-semibold text-foreground'>{preferencesConfig.dateFormat}</span>
                </div>
              </div>
              <Button
                variant='outline'
                onClick={() => setActiveConfigModal('preferences')}
                className='w-full justify-between hover:bg-brand-cornflower/5 text-sm font-medium'
              >
                Change Localization & Preferences
                <Icons.chevronRight className='h-4 w-4 text-muted-foreground' />
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Quick Toggles */}
      <motion.div variants={itemVariants}>
        <Card className='border-border/80 shadow-sm'>
          <CardHeader>
            <CardTitle className='text-base font-bold text-brand-navy'>Quick Toggles</CardTitle>
            <CardDescription>Instant toggles for notification alerts and UI behavior</CardDescription>
          </CardHeader>
          <CardContent className='divide-y divide-gray-100'>
            <div className='flex items-center justify-between py-3'>
              <div className='space-y-0.5'>
                <Label className='text-sm font-semibold text-foreground cursor-pointer'>Email Notifications</Label>
                <p className='text-xs text-muted-foreground'>Receive immediate email notifications for ticket assignments</p>
              </div>
              <Switch
                checked={quickSettings.emailNotifications}
                onCheckedChange={(val) => handleQuickToggle('emailNotifications', val)}
              />
            </div>
            <div className='flex items-center justify-between py-3'>
              <div className='space-y-0.5'>
                <Label className='text-sm font-semibold text-foreground cursor-pointer'>Desktop Alerts</Label>
                <p className='text-xs text-muted-foreground'>Show pop-up notifications when high-priority tickets escalate</p>
              </div>
              <Switch
                checked={quickSettings.desktopNotifications}
                onCheckedChange={(val) => handleQuickToggle('desktopNotifications', val)}
              />
            </div>
            <div className='flex items-center justify-between py-3'>
              <div className='space-y-0.5'>
                <Label className='text-sm font-semibold text-foreground cursor-pointer'>Weekly AI Activity Digest</Label>
                <p className='text-xs text-muted-foreground'>Receive weekly summary report of AI resolution metrics</p>
              </div>
              <Switch
                checked={quickSettings.weeklyDigest}
                onCheckedChange={(val) => handleQuickToggle('weeklyDigest', val)}
              />
            </div>
            <div className='flex items-center justify-between py-3'>
              <div className='space-y-0.5'>
                <Label className='text-sm font-semibold text-foreground cursor-pointer'>Sound Effects</Label>
                <p className='text-xs text-muted-foreground'>Play audible chime when live status diagnostics update</p>
              </div>
              <Switch
                checked={quickSettings.soundEffects}
                onCheckedChange={(val) => handleQuickToggle('soundEffects', val)}
              />
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Danger Zone */}
      <motion.div variants={itemVariants}>
        <Card className='border-red-200 bg-red-50/30 shadow-sm'>
          <CardHeader>
            <CardTitle className='text-base font-bold text-red-600 flex items-center gap-2'>
              <Icons.alertTriangle className='h-4 w-4' />
              Danger Zone
            </CardTitle>
            <CardDescription className='text-xs text-red-600/80'>
              Actions here cannot be undone. Please proceed with caution.
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4'>
            <div>
              <p className='text-sm font-bold text-foreground'>Delete Account</p>
              <p className='text-xs text-muted-foreground'>
                Permanently purge your AutoPilot user profile and active workspace credentials.
              </p>
            </div>
            <Button
              variant='outline'
              onClick={() => setIsDeleteAccountOpen(true)}
              className='border-red-200 text-red-600 hover:bg-red-600 hover:text-white transition-all text-xs font-semibold'
            >
              Delete Account
            </Button>
          </CardContent>
        </Card>
      </motion.div>

      {/* MODAL 1: Edit Profile */}
      <Dialog open={isEditProfileOpen} onOpenChange={setIsEditProfileOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Profile Information</DialogTitle>
            <DialogDescription>Update your display name, department, and contact info.</DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium'>Display Name</Label>
              <Input
                value={editProfileForm.name}
                onChange={(e) => setEditProfileForm({ ...editProfileForm, name: e.target.value })}
              />
            </div>
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium'>Email Address</Label>
              <Input
                value={editProfileForm.email}
                onChange={(e) => setEditProfileForm({ ...editProfileForm, email: e.target.value })}
              />
            </div>
            <div className='grid grid-cols-2 gap-4'>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium'>Department</Label>
                <Input
                  value={editProfileForm.department}
                  onChange={(e) => setEditProfileForm({ ...editProfileForm, department: e.target.value })}
                />
              </div>
              <div className='space-y-1.5'>
                <Label className='text-xs font-medium'>Location</Label>
                <Input
                  value={editProfileForm.location}
                  onChange={(e) => setEditProfileForm({ ...editProfileForm, location: e.target.value })}
                />
              </div>
            </div>
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium'>Title / Role</Label>
              <Input
                value={editProfileForm.title}
                onChange={(e) => setEditProfileForm({ ...editProfileForm, title: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setIsEditProfileOpen(false)}>Cancel</Button>
            <Button onClick={handleSaveProfile} className='bg-brand-cornflower text-white hover:bg-brand-cornflower/90'>
              Save Profile
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 2: Notifications Configurer */}
      <Dialog open={activeConfigModal === 'notifications'} onOpenChange={() => setActiveConfigModal(null)}>
        <DialogContent className='max-w-md'>
          <DialogHeader>
            <DialogTitle>Notification Preferences</DialogTitle>
            <DialogDescription>Configure quiet hours, alert sensitivity, and webhooks.</DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            <div className='flex items-center justify-between'>
              <div>
                <Label className='text-sm font-semibold'>Enable Quiet Hours</Label>
                <p className='text-xs text-muted-foreground'>Mute non-urgent notifications during off-hours</p>
              </div>
              <Switch
                checked={notificationsConfig.quietHours}
                onCheckedChange={(val) => setNotificationsConfig({ ...notificationsConfig, quietHours: val })}
              />
            </div>
            {notificationsConfig.quietHours && (
              <div className='grid grid-cols-2 gap-3 pt-1'>
                <div>
                  <Label className='text-xs font-medium'>Quiet Start</Label>
                  <Input
                    type='time'
                    value={notificationsConfig.quietStart}
                    onChange={(e) => setNotificationsConfig({ ...notificationsConfig, quietStart: e.target.value })}
                  />
                </div>
                <div>
                  <Label className='text-xs font-medium'>Quiet End</Label>
                  <Input
                    type='time'
                    value={notificationsConfig.quietEnd}
                    onChange={(e) => setNotificationsConfig({ ...notificationsConfig, quietEnd: e.target.value })}
                  />
                </div>
              </div>
            )}
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium'>Slack Webhook URL</Label>
              <Input
                value={notificationsConfig.slackWebhook}
                onChange={(e) => setNotificationsConfig({ ...notificationsConfig, slackWebhook: e.target.value })}
                placeholder='https://hooks.slack.com/...'
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setActiveConfigModal(null)}>Cancel</Button>
            <Button
              onClick={() => {
                localStorage.setItem('autopilot_notifs_config', JSON.stringify(notificationsConfig))
                setActiveConfigModal(null)
                showToast('Notification preferences saved!')
              }}
              className='bg-brand-cornflower text-white'
            >
              Save Preferences
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 3: Security & Password */}
      <Dialog open={activeConfigModal === 'security'} onOpenChange={() => setActiveConfigModal(null)}>
        <DialogContent className='max-w-lg'>
          <DialogHeader>
            <DialogTitle>Security & Access Control</DialogTitle>
            <DialogDescription>Update your password, toggle 2FA, or revoke active sessions.</DialogDescription>
          </DialogHeader>
          <div className='space-y-6 py-2'>
            {/* Password Change */}
            <div className='space-y-3 border-b pb-4'>
              <h4 className='text-sm font-bold text-foreground'>Change Password</h4>
              <div className='space-y-2'>
                <Input
                  type='password'
                  placeholder='Current Password'
                  value={passwordForm.current}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current: e.target.value })}
                />
                <Input
                  type='password'
                  placeholder='New Password (min 8 chars)'
                  value={passwordForm.new}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new: e.target.value })}
                />
                <Input
                  type='password'
                  placeholder='Confirm New Password'
                  value={passwordForm.confirm}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })}
                />
                <Button size='sm' onClick={handleChangePassword} className='bg-brand-navy text-white text-xs'>
                  Update Password
                </Button>
              </div>
            </div>

            {/* 2FA Toggle */}
            <div className='flex items-center justify-between border-b pb-4'>
              <div>
                <h4 className='text-sm font-bold text-foreground'>Two-Factor Authentication (2FA)</h4>
                <p className='text-xs text-muted-foreground'>Require authenticator app code on login</p>
              </div>
              <Switch
                checked={securityConfig.twoFactorEnabled}
                onCheckedChange={(val) => {
                  const updated = { ...securityConfig, twoFactorEnabled: val }
                  setSecurityConfig(updated)
                  localStorage.setItem('autopilot_sec_config', JSON.stringify(updated))
                  showToast(val ? '2FA Enabled' : '2FA Disabled', val ? 'success' : 'info')
                }}
              />
            </div>

            {/* Active Sessions */}
            <div className='space-y-2'>
              <h4 className='text-sm font-bold text-foreground'>Active Login Sessions</h4>
              <div className='space-y-2 max-h-48 overflow-y-auto pr-1'>
                {securityConfig.sessions.map((sess) => (
                  <div key={sess.id} className='flex items-center justify-between p-2.5 rounded-lg border bg-gray-50 text-xs'>
                    <div>
                      <p className='font-semibold text-foreground flex items-center gap-1.5'>
                        <Icons.device className='h-3.5 w-3.5 text-gray-500' />
                        {sess.device}
                        {sess.current && <span className='text-[10px] bg-emerald-100 text-emerald-700 px-1.5 py-0.2 rounded font-bold'>Current</span>}
                      </p>
                      <p className='text-muted-foreground text-[11px]'>{sess.location} • {sess.lastActive}</p>
                    </div>
                    {!sess.current && (
                      <Button
                        size='sm'
                        variant='ghost'
                        onClick={() => handleRevokeSession(sess.id)}
                        className='text-red-600 hover:bg-red-50 text-xs h-7 px-2'
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setActiveConfigModal(null)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 4: Integrations */}
      <Dialog open={activeConfigModal === 'integrations'} onOpenChange={() => setActiveConfigModal(null)}>
        <DialogContent className='max-w-md'>
          <DialogHeader>
            <DialogTitle>Manage Integrations</DialogTitle>
            <DialogDescription>Configure tokens and status for third-party platforms.</DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            {Object.entries(integrationsConfig).map(([key, item]) => (
              <div key={key} className='space-y-2 p-3 rounded-lg border bg-gray-50/70'>
                <div className='flex items-center justify-between'>
                  <span className='font-bold text-sm capitalize text-brand-navy'>{key}</span>
                  <Switch
                    checked={item.connected}
                    onCheckedChange={(val) => {
                      const updated = {
                        ...integrationsConfig,
                        [key]: { ...item, connected: val },
                      }
                      setIntegrationsConfig(updated)
                      localStorage.setItem('autopilot_integ_config', JSON.stringify(updated))
                      showToast(`${key.toUpperCase()} integration ${val ? 'connected' : 'disconnected'}`)
                    }}
                  />
                </div>
                {item.connected && (
                  <Input
                    type='password'
                    value={item.token}
                    placeholder={`${key} API token`}
                    onChange={(e) => {
                      const updated = {
                        ...integrationsConfig,
                        [key]: { ...item, token: e.target.value },
                      }
                      setIntegrationsConfig(updated)
                    }}
                    className='text-xs font-mono bg-white'
                  />
                )}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setActiveConfigModal(null)}>Close</Button>
            <Button
              onClick={() => {
                localStorage.setItem('autopilot_integ_config', JSON.stringify(integrationsConfig))
                setActiveConfigModal(null)
                showToast('Integration settings saved!')
              }}
              className='bg-brand-cornflower text-white'
            >
              Save Integrations
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 5: Preferences (Language & Timezone) */}
      <Dialog open={activeConfigModal === 'preferences'} onOpenChange={() => setActiveConfigModal(null)}>
        <DialogContent className='max-w-md'>
          <DialogHeader>
            <DialogTitle>Localization & Preferences</DialogTitle>
            <DialogDescription>Customize timezone, language, and date display options.</DialogDescription>
          </DialogHeader>
          <div className='space-y-4 py-2'>
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium'>Timezone</Label>
              <Select
                value={preferencesConfig.timezone}
                onValueChange={(val) => setPreferencesConfig({ ...preferencesConfig, timezone: val })}
              >
                <SelectTrigger>
                  <SelectValue placeholder='Select timezone' />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='Asia/Kuala_Lumpur'>Asia/Kuala_Lumpur (GMT+8)</SelectItem>
                  <SelectItem value='Asia/Singapore'>Asia/Singapore (GMT+8)</SelectItem>
                  <SelectItem value='UTC'>UTC (GMT+0)</SelectItem>
                  <SelectItem value='America/New_York'>America/New_York (GMT-5)</SelectItem>
                  <SelectItem value='Europe/London'>Europe/London (GMT+0)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className='space-y-1.5'>
              <Label className='text-xs font-medium'>Date Format</Label>
              <Select
                value={preferencesConfig.dateFormat}
                onValueChange={(val) => setPreferencesConfig({ ...preferencesConfig, dateFormat: val })}
              >
                <SelectTrigger>
                  <SelectValue placeholder='Select format' />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value='YYYY-MM-DD'>YYYY-MM-DD (ISO standard)</SelectItem>
                  <SelectItem value='DD/MM/YYYY'>DD/MM/YYYY (UK / MY)</SelectItem>
                  <SelectItem value='MM/DD/YYYY'>MM/DD/YYYY (US format)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setActiveConfigModal(null)}>Cancel</Button>
            <Button
              onClick={() => {
                localStorage.setItem('autopilot_pref_config', JSON.stringify(preferencesConfig))
                setActiveConfigModal(null)
                showToast('Preferences updated!')
              }}
              className='bg-brand-cornflower text-white'
            >
              Save Preferences
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 6: Reset Confirmation */}
      <Dialog open={isResetConfirmOpen} onOpenChange={setIsResetConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset All Settings?</DialogTitle>
            <DialogDescription>
              This will restore all notifications, quick toggles, security options, and preferences to default factory values.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant='outline' onClick={() => setIsResetConfirmOpen(false)}>Cancel</Button>
            <Button onClick={handleResetAllSettings} className='bg-amber-600 text-white hover:bg-amber-700'>
              Reset Defaults
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* MODAL 7: Delete Account Confirmation */}
      <Dialog open={isDeleteAccountOpen} onOpenChange={setIsDeleteAccountOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className='text-red-600'>Confirm Account Deletion</DialogTitle>
            <DialogDescription>
              Are you absolutely sure? Type <strong className='text-foreground font-mono'>DELETE</strong> below to confirm.
            </DialogDescription>
          </DialogHeader>
          <div className='py-2'>
            <Input
              value={deleteConfirmText}
              placeholder='Type DELETE'
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              className='font-mono'
            />
          </div>
          <DialogFooter>
            <Button variant='outline' onClick={() => setIsDeleteAccountOpen(false)}>Cancel</Button>
            <Button
              disabled={deleteConfirmText !== 'DELETE'}
              onClick={handleDeleteAccount}
              className='bg-red-600 text-white hover:bg-red-700 disabled:opacity-50'
            >
              Permanently Delete Account
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  )
}
