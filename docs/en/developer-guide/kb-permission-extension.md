---
sidebar_position: 3
---

# Knowledge Base Permission Extension

This document describes how to extend the knowledge base permission system with custom permission tabs, such as department-level permissions via external ERP systems.

## Overview

The knowledge base permission system provides an extension point that allows you to add additional permission management tabs beyond the default personal permissions tab. This is useful for integrating with external permission systems like ERP (Enterprise Resource Planning) or other enterprise identity management systems.

## Extension Point

The extension is implemented through the `ExtensionTabConfig` interface and the `KbPermissionsPanel` component.

### ExtensionTabConfig Interface

```typescript
interface ExtensionTabConfig {
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
```

### Basic Usage

To add a custom permission tab, wrap the `KnowledgeDetailPanel` component and inject your extension tabs:

```typescript
'use client'

import { Building2 } from 'lucide-react'
import { KnowledgeDetailPanel, type ExtensionTabConfig } from '@/features/knowledge'

// Your custom permission management component
function DepartmentPermissionTab({ kbId }: { kbId: number }) {
  // Implement your department permission UI here
  return <div>Department permissions for KB {kbId}</div>
}

// Define the extension tab
const departmentExtensionTab: ExtensionTabConfig = {
  id: 'department',
  label: 'Department',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true,
}

// Extended knowledge detail panel
interface ExtendedKnowledgeDetailPanelProps {
  selectedKb: KnowledgeBase | null
  // ... other props
}

export function ExtendedKnowledgeDetailPanel(props: ExtendedKnowledgeDetailPanelProps) {
  return (
    <KnowledgeDetailPanel
      {...props}
      permissionExtensionTabs={[departmentExtensionTab]}
    />
  )
}
```

## Implementation Guide

### Step 1: Create Your Permission Component

Create a component that implements your custom permission logic:

```typescript
// features/knowledge/extensions/DepartmentPermissionTab.tsx
'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface DepartmentPermissionTabProps {
  kbId: number
}

export function DepartmentPermissionTab({ kbId }: DepartmentPermissionTabProps) {
  const [permissions, setPermissions] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Fetch department permissions for this knowledge base
    fetchDepartmentPermissions(kbId).then(setPermissions)
  }, [kbId])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">Department Permissions</h3>
        <Button>Add Department</Button>
      </div>
      {/* Render your permission management UI */}
      {permissions.map(dept => (
        <Card key={dept.id}>{dept.name}</Card>
      ))}
    </div>
  )
}
```

### Step 2: Configure the Extension Tab

Define your extension tab configuration:

```typescript
import { Building2 } from 'lucide-react'
import type { ExtensionTabConfig } from '@/features/knowledge'
import { DepartmentPermissionTab } from './DepartmentPermissionTab'

export const departmentExtensionTab: ExtensionTabConfig = {
  id: 'department',
  label: 'Department',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true, // Only show for users with manage permission
}
```

### Step 3: Inject into KnowledgeDetailPanel

Wrap the `KnowledgeDetailPanel` to inject your extension:

```typescript
// features/knowledge/extensions/ExtendedKnowledgeDetailPanel.tsx
import { KnowledgeDetailPanel, type ExtensionTabConfig } from '@/features/knowledge'
import { departmentExtensionTab } from './departmentExtensionTab'

interface ExtendedKnowledgeDetailPanelProps {
  selectedKb: KnowledgeBase | null
  // ... other props from KnowledgeDetailPanelProps
}

export function ExtendedKnowledgeDetailPanel(props: ExtendedKnowledgeDetailPanelProps) {
  return (
    <KnowledgeDetailPanel
      {...props}
      permissionExtensionTabs={[departmentExtensionTab]}
    />
  )
}
```

## Backend Integration

Your custom permission tab should integrate with the backend through the `IKbPermissionResolver` interface. See the [backend documentation](../../concepts/permission-system.md) for details.

### API Endpoints

You should create the following API endpoints for your custom permission system:

- `GET /api/knowledge-bases/{kb_id}/department-permissions` - List department permissions
- `POST /api/knowledge-bases/{kb_id}/department-permissions` - Add department permission
- `DELETE /api/knowledge-bases/{kb_id}/department-permissions/{id}` - Remove department permission

### Backend Extension

Implement the `IKbPermissionResolver` interface in your backend:

```python
# backend/app/extensions/myext/kb_permissions.py
from app.services.readers.kb_permissions import IKbPermissionResolver

class DepartmentPermissionResolver(IKbPermissionResolver):
    def __init__(self, base: IKbPermissionResolver):
        self._base = base

    def resolve(self, db, kb_id, user_id, kb):
        # Check if user has access via department
        if self._has_department_access(db, kb_id, user_id):
            return "Developer"
        return self._base.resolve(db, kb_id, user_id, kb)

    def get_accessible_kb_ids(self, db, user_id):
        # Return KB IDs accessible via department
        dept_ids = self._get_dept_accessible_kbs(db, user_id)
        base_ids = self._base.get_accessible_kb_ids(db, user_id)
        return list(set(dept_ids + base_ids))
```

Register the extension via Python entry points in your `pyproject.toml`:

```toml
[project.entry-points."wegent.kb_permissions"]
department = "app.extensions.myext.kb_permissions:DepartmentPermissionResolver"
```

## Examples

### ERP Department Permissions

```typescript
import { Building2 } from 'lucide-react'
import { useTranslation } from '@/hooks/useTranslation'
import { useErpDepartments } from './hooks/useErpDepartments'

function ErpDeptTab({ kbId }: { kbId: number }) {
  const { t } = useTranslation('knowledge')
  const { departments, loading, addDepartment, removeDepartment } = useErpDepartments(kbId)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">{t('document.permission.erpDepartments')}</h3>
        <AddDepartmentDialog kbId={kbId} onAdd={addDepartment} />
      </div>
      {/* List of authorized departments */}
    </div>
  )
}

export const erpExtensionTab: ExtensionTabConfig = {
  id: 'department',
  label: 'Department',
  icon: Building2,
  component: ErpDeptTab,
  requiresManagePermission: true,
}
```

### Multiple Extension Tabs

You can add multiple extension tabs:

```typescript
const extensionTabs: ExtensionTabConfig[] = [
  {
    id: 'department',
    label: 'Department',
    icon: Building2,
    component: DepartmentTab,
    requiresManagePermission: true,
  },
  {
    id: 'employee',
    label: 'Employee',
    icon: Users,
    component: EmployeeTab,
    requiresManagePermission: true,
  },
]

<KnowledgeDetailPanel
  selectedKb={selectedKb}
  permissionExtensionTabs={extensionTabs}
/>
```

## Best Practices

1. **Unique IDs**: Ensure your extension tab IDs are unique to avoid conflicts.

2. **Permission Checks**: Use `requiresManagePermission` appropriately to hide tabs from users without management rights.

3. **Lazy Loading**: For heavy components, use dynamic imports:

   ```typescript
   const DepartmentTab = lazy(() => import('./DepartmentTab'))
   ```

4. **Error Boundaries**: Wrap your extension components with error boundaries to prevent crashes from affecting the entire panel.

5. **Consistent Styling**: Use the project's design system components (Card, Button, etc.) for consistent UI.

6. **i18n Support**: Use the `useTranslation` hook for all user-facing text.

## Troubleshooting

### Extension Tab Not Showing

- Check that the tab ID is unique
- Verify `requiresManagePermission` logic if applicable
- Ensure the component is properly exported and imported

### Permission Not Applied

- Verify the backend `IKbPermissionResolver` implementation
- Check that the entry point is correctly registered in `pyproject.toml`
- Review backend logs for extension loading errors

### Type Errors

- Ensure `ExtensionTabConfig` is imported from the correct location
- Verify the component prop types match `{ kbId: number }`

## See Also

- [Permission System Concepts](../../concepts/permission-system.md)
- [Backend Extension Guide](../backend-extensions.md)
- [Component Design Guidelines](../component-design.md)
