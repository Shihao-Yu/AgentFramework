import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useSettings, type Settings } from '@/hooks/useSettings'
import { Loader2 } from 'lucide-react'

export function SettingsPage() {
  const { settings, isLoading, error, updateSettings } = useSettings()
  const [localSettings, setLocalSettings] = useState<Settings | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (settings) {
      setLocalSettings(settings)
    }
  }, [settings])

  const hasChanges = localSettings && settings && 
    JSON.stringify(localSettings) !== JSON.stringify(settings)

  const handleSave = async () => {
    if (!localSettings) return
    
    setIsSaving(true)
    setSaveMessage(null)
    
    try {
      await updateSettings(localSettings)
      setSaveMessage({ type: 'success', text: 'Settings saved successfully' })
      setTimeout(() => setSaveMessage(null), 3000)
    } catch {
      setSaveMessage({ type: 'error', text: 'Failed to save settings' })
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading && !localSettings) {
    return (
      <div className="p-6 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error && !localSettings) {
    return (
      <div className="p-6">
        <div className="text-destructive">Error loading settings: {error}</div>
      </div>
    )
  }

  if (!localSettings) return null

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Configure knowledge base settings and preferences.
        </p>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Search Configuration</CardTitle>
            <CardDescription>
              Adjust search behavior and result preferences.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bm25-weight">BM25 Weight</Label>
                <Input
                  id="bm25-weight"
                  type="number"
                  value={localSettings.search.bm25_weight}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    search: { ...localSettings.search, bm25_weight: parseFloat(e.target.value) || 0 }
                  })}
                  step="0.1"
                  min="0"
                  max="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="vector-weight">Vector Weight</Label>
                <Input
                  id="vector-weight"
                  type="number"
                  value={localSettings.search.vector_weight}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    search: { ...localSettings.search, vector_weight: parseFloat(e.target.value) || 0 }
                  })}
                  step="0.1"
                  min="0"
                  max="1"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="result-limit">Default Result Limit</Label>
              <Select
                value={String(localSettings.search.default_limit)}
                onValueChange={(value) => setLocalSettings({
                  ...localSettings,
                  search: { ...localSettings.search, default_limit: parseInt(value) }
                })}
              >
                <SelectTrigger id="result-limit">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">5 results</SelectItem>
                  <SelectItem value="10">10 results</SelectItem>
                  <SelectItem value="20">20 results</SelectItem>
                  <SelectItem value="50">50 results</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pipeline Configuration</CardTitle>
            <CardDescription>
              Configure ticket-to-FAQ pipeline behavior.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="skip-threshold">Skip Threshold</Label>
                <Input
                  id="skip-threshold"
                  type="number"
                  value={localSettings.pipeline.similarity_skip_threshold}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    pipeline: { ...localSettings.pipeline, similarity_skip_threshold: parseFloat(e.target.value) || 0 }
                  })}
                  step="0.05"
                  min="0"
                  max="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="variant-threshold">Variant Threshold</Label>
                <Input
                  id="variant-threshold"
                  type="number"
                  value={localSettings.pipeline.similarity_variant_threshold}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    pipeline: { ...localSettings.pipeline, similarity_variant_threshold: parseFloat(e.target.value) || 0 }
                  })}
                  step="0.05"
                  min="0"
                  max="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="merge-threshold">Merge Threshold</Label>
                <Input
                  id="merge-threshold"
                  type="number"
                  value={localSettings.pipeline.similarity_merge_threshold}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    pipeline: { ...localSettings.pipeline, similarity_merge_threshold: parseFloat(e.target.value) || 0 }
                  })}
                  step="0.05"
                  min="0"
                  max="1"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="confidence-threshold">Confidence Threshold</Label>
                <Input
                  id="confidence-threshold"
                  type="number"
                  value={localSettings.pipeline.confidence_threshold}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    pipeline: { ...localSettings.pipeline, confidence_threshold: parseFloat(e.target.value) || 0 }
                  })}
                  step="0.05"
                  min="0"
                  max="1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="min-body-length">Min Body Length</Label>
                <Input
                  id="min-body-length"
                  type="number"
                  value={localSettings.pipeline.min_body_length}
                  onChange={(e) => setLocalSettings({
                    ...localSettings,
                    pipeline: { ...localSettings.pipeline, min_body_length: parseInt(e.target.value) || 1 }
                  })}
                  min="1"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Maintenance</CardTitle>
            <CardDescription>
              Data retention and cleanup settings.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="version-retention">Version History Retention</Label>
                <Select
                  value={String(localSettings.maintenance.version_retention_days)}
                  onValueChange={(value) => setLocalSettings({
                    ...localSettings,
                    maintenance: { ...localSettings.maintenance, version_retention_days: parseInt(value) }
                  })}
                >
                  <SelectTrigger id="version-retention">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 days</SelectItem>
                    <SelectItem value="60">60 days</SelectItem>
                    <SelectItem value="90">90 days</SelectItem>
                    <SelectItem value="180">180 days</SelectItem>
                    <SelectItem value="365">1 year</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="hit-retention">Hit Data Retention</Label>
                <Select
                  value={String(localSettings.maintenance.hit_retention_days)}
                  onValueChange={(value) => setLocalSettings({
                    ...localSettings,
                    maintenance: { ...localSettings.maintenance, hit_retention_days: parseInt(value) }
                  })}
                >
                  <SelectTrigger id="hit-retention">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="30">30 days</SelectItem>
                    <SelectItem value="90">90 days</SelectItem>
                    <SelectItem value="180">180 days</SelectItem>
                    <SelectItem value="365">1 year</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        <Separator />

        <div className="flex items-center justify-between">
          <div>
            {saveMessage && (
              <span className={saveMessage.type === 'success' ? 'text-green-600' : 'text-destructive'}>
                {saveMessage.text}
              </span>
            )}
          </div>
          <Button onClick={handleSave} disabled={!hasChanges || isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {hasChanges ? 'Save Settings' : 'No Changes'}
          </Button>
        </div>
      </div>
    </div>
  )
}
