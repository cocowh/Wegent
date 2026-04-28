// SPDX-FileCopyrightText: 2025 Wegent, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * KbPermissionsPanel renders the permission management panel for a knowledge base.
 *
 * This component provides an extension point for adding additional permission tabs
 * (e.g., department-level permissions via external ERP systems). By default, it
 * only shows the personal permission management tab.
 *
 * Extension Example:
 * ```typescript
 * import { Building2 } from 'lucide-react'
 * import { ErpDeptTab } from '@wecode/features/knowledge/components'
 *
 * const erpExtensionTab: ExtensionTabConfig = {
 *   id: 'department',
 *   label: 'Department',
 *   icon: Building2,
 *   component: ErpDeptTab,
 *   requiresManagePermission: true,
 * }
 *
 * <KbPermissionsPanel
 *   kbId={kbId}
 *   canManagePermissions={canManagePermissions}
 *   extensionTabs={[erpExtensionTab]}
 * />
 * ```
 */

'use client'

import { useState, useMemo } from 'react'
import { Users } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useTranslation } from '@/hooks/useTranslation'
import { PermissionManagementTab } from './PermissionManagementTab'

/**
 * Configuration for an extension permission tab.
 */
export interface ExtensionTabConfig {
  /** Unique identifier for this tab */
  id: string
  /** Display label for the tab */
  label: string
  /** Lucide icon component */
  icon: React.ComponentType<{ className?: string }>
  /** Component to render as tab content, receives kbId prop */
  component: React.ComponentType<{ kbId: number }>
  /** Whether this tab requires manage permission to be visible */
  requiresManagePermission?: boolean
}

interface KbPermissionsPanelProps {
  /** Knowledge base ID */
  kbId: number
  /** Whether the current user can manage permissions */
  canManagePermissions: boolean
  /** Additional permission tabs injected by extensions */
  extensionTabs?: ExtensionTabConfig[]
}

/**
 * Knowledge base permissions panel with support for extension tabs.
 *
 * By default, only shows the personal permission management tab. Extensions can
 * provide additional tabs (e.g., department permissions) via the extensionTabs prop.
 */
export function KbPermissionsPanel({
  kbId,
  canManagePermissions,
  extensionTabs = [],
}: KbPermissionsPanelProps) {
  const { t } = useTranslation('knowledge')

  // Build list of all visible tabs
  const visibleTabs = useMemo(() => {
    const tabs = [
      {
        id: 'personal',
        label: t('document.permission.personal') || 'Personal',
        icon: Users,
        component: PermissionManagementTab,
        requiresManagePermission: false,
      },
      ...extensionTabs.filter(
        tab => !tab.requiresManagePermission || canManagePermissions
      ),
    ]
    return tabs
  }, [extensionTabs, canManagePermissions, t])

  const [activeTab, setActiveTab] = useState(visibleTabs[0]?.id || 'personal')

  // Single tab mode: no tabs UI, just render the content
  if (visibleTabs.length === 1) {
    const TabComponent = visibleTabs[0].component
    return <TabComponent kbId={kbId} />
  }

  // Multi-tab mode: render tabs
  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="h-8">
          {visibleTabs.map(tab => {
            const Icon = tab.icon
            return (
              <TabsTrigger
                key={tab.id}
                value={tab.id}
                className="gap-1 h-7 px-3 text-xs"
                data-testid={`permission-tab-${tab.id}`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </TabsTrigger>
            )
          })}
        </TabsList>

        {visibleTabs.map(tab => {
          const TabComponent = tab.component
          return (
            <TabsContent key={tab.id} value={tab.id} className="mt-4">
              <TabComponent kbId={kbId} />
            </TabsContent>
          )
        })}
      </Tabs>
    </div>
  )
}
