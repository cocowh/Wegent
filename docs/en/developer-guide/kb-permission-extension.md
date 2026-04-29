---
sidebar_position: 3
---

# Knowledge Base Extension System

This document describes the knowledge base extension system, which provides multiple extension points for integrating external systems (such as ERP, department management, or custom permission systems) without modifying the open-source codebase.

## Overview

The knowledge base extension system uses a **registry + bridge** pattern: open-source components provide well-defined extension points, and external packages register their implementations during application initialization. This achieves clean separation between open-source and proprietary code.

The system includes the following extension mechanisms:

| Extension Point | Pattern | Description |
|----------------|---------|-------------|
| [Component Registry](#component-registry) | Override | Replace entire components (DocumentPanel, KnowledgeDetailPanel) |
| [External Binding API](#external-binding-api) | Provider + Bridge | Search, add, remove, and sync external entity bindings |
| [Permission Extension Tabs](#permission-extension-tabs) | Prop Injection | Add custom permission management tabs |
| [Create KB Dialog Form Sections](#create-kb-dialog-extension) | State Bridge | Inject form sections at well-defined slot positions |
| [Post-Creation Hooks](#post-creation-hook) | State Bridge | Run async operations after KB creation |
| [Custom Role Select](#role-select-extension) | Component Bridge | Replace the role select dropdown in AddUserForm |

## Component Registry

The component registry allows external packages to override entire knowledge document components at runtime.

### Registry Interface

```typescript
// frontend/src/features/knowledge/document/components/registry.ts

export interface ComponentRegistry {
  /** Document panel component for notebook KB right panel */
  DocumentPanel?: ComponentType<DocumentPanelProps>
  /** Knowledge detail panel component for classic KB detail view */
  KnowledgeDetailPanel?: ComponentType<KnowledgeDetailPanelProps>
}
```

### Registration

Call `registerComponents()` during application initialization, before any components are rendered:

```typescript
import { registerComponents } from '@/features/knowledge/document/components'
import { CustomDocumentPanel } from './CustomDocumentPanel'

registerComponents({
  DocumentPanel: CustomDocumentPanel,
})
```

### Resolution

Open-source components use `getComponent()` to resolve registered components at **render time** (not at module load time), giving external packages time to populate the registry first:

```typescript
import { getComponent } from '@/features/knowledge/document/components'
import { DocumentPanel as DefaultDocumentPanel } from './DocumentPanel'
import type { DocumentPanelProps } from './DocumentPanel'

function DocumentPanel(props: DocumentPanelProps) {
  const Panel = useMemo(
    () => getComponent('DocumentPanel', DefaultDocumentPanel),
    []
  )
  return <Panel {...props} />
}
```

### Utility Functions

```typescript
/** Check if a component has been registered */
function hasComponent(name: keyof ComponentRegistry): boolean

/** Clear all registered components (useful for testing) */
function clearRegistry(): void
```

## External Binding API

The external binding API allows external packages to bind external system entities (departments, employees, customers, etc.) to knowledge bases.

### Architecture

The binding system consists of two parts:

1. **Binding Provider Registry** — Declares available external systems and their search capabilities
2. **External Binding API** — Provides CRUD operations for bindings

### Binding Provider Types

```typescript
// frontend/src/apis/knowledgeExtensions.ts

export interface BindableItem {
  id: string
  name: string
  fullPath?: string    // Hierarchy path, e.g., "Dept A / Team B"
  avatar?: string
  metadata?: Record<string, unknown>
}

export interface BindableTypeConfig {
  type: string           // e.g., 'department', 'employee', 'customer'
  displayName: string
  icon?: string
  allowMultiple: boolean
}

export interface BindingProvider {
  name: string                   // Unique identifier, e.g., 'erp', 'oa'
  displayName: string
  icon?: string
  searchable: boolean
  bindableTypes: BindableTypeConfig[]
  search: (keyword: string, type?: string) => Promise<BindingSearchResult>
  validate: (externalId: string, type: string) => Promise<boolean>
  getItemDetails?: (externalId: string, type: string) => Promise<BindableItem | null>
}
```

### External Binding Data Model

```typescript
export interface ExternalBinding {
  id: number
  kbId: number
  provider: string
  bindableType: string
  externalId: string
  name: string
  fullPath?: string
  avatar?: string
  metadata?: Record<string, unknown>
  createdAt: string
}

export interface ExternalBindingCreate {
  provider: string
  bindableType: string
  externalId: string
}
```

### External Binding API Interface

```typescript
export interface ExternalBindingApi {
  readonly providers: BindingProviderRegistry

  search: (
    keyword: string,
    provider?: string,
    type?: string
  ) => Promise<Record<string, BindingSearchResult>>

  list: (kbId: number, provider?: string) => Promise<ExternalBinding[]>
  add: (kbId: number, data: ExternalBindingCreate) => Promise<ExternalBinding>
  remove: (kbId: number, bindingId: number) => Promise<void>
  sync: (kbId: number, bindingId: number) => Promise<void>
}
```

### Usage

External packages register providers and set the API implementation during app initialization:

```typescript
import {
  bindingProviderRegistry,
  setExternalBindingApi,
  type BindingProvider,
} from '@/apis/knowledgeExtensions'

// Register a binding provider (e.g., ERP department search)
bindingProviderRegistry.register({
  name: 'erp',
  displayName: 'ERP System',
  searchable: true,
  bindableTypes: [
    { type: 'department', displayName: 'Department', allowMultiple: true },
  ],
  search: async (keyword, type) => {
    // Search ERP API for departments/employees
    return { items: [...], hasMore: false }
  },
  validate: async (externalId, type) => {
    // Validate external ID
    return true
  },
})

// Set the binding API implementation
setExternalBindingApi({
  providers: bindingProviderRegistry,
  search: async (keyword, provider, type) => { /* ... */ },
  list: async (kbId, provider) => { /* ... */ },
  add: async (kbId, data) => { /* ... */ },
  remove: async (kbId, bindingId) => { /* ... */ },
  sync: async (kbId, bindingId) => { /* ... */ },
})
```

### Accessing the API

Open-source components check availability and access the API safely:

```typescript
import {
  hasExternalBindingApi,
  getExternalBindingApi,
} from '@/apis/knowledgeExtensions'

if (hasExternalBindingApi()) {
  const api = getExternalBindingApi()
  const bindings = await api.list(kbId)
}
```

## Permission Extension Tabs

The `KbPermissionsPanel` component provides an `extensionTabs` prop to add additional permission management tabs beyond the default personal permissions tab.

### ExtensionTabConfig Interface

```typescript
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
```

### Usage

```typescript
import { Building2 } from 'lucide-react'
import { KbPermissionsPanel, type ExtensionTabConfig } from '@/features/knowledge/permission/components'

const departmentTab: ExtensionTabConfig = {
  id: 'department',
  label: 'Department',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true,
}

// In your component:
<KbPermissionsPanel
  kbId={kbId}
  canManagePermissions={canManagePermissions}
  extensionTabs={[departmentTab]}
/>
```

The `KnowledgeDetailPanel` component also exposes this via the `permissionExtensionTabs` prop:

```typescript
<KnowledgeDetailPanel
  selectedKb={selectedKb}
  permissionExtensionTabs={[departmentTab]}
/>
```

## Create KB Dialog Extension

The create KB dialog (`CreateKnowledgeBaseDialog`) provides two extension mechanisms: form section injection and post-creation hooks.

### Form Sections

The `KnowledgeBaseForm` component defines well-defined slot positions for external packages to inject custom UI sections:

```typescript
export interface KnowledgeBaseFormSections {
  /** Rendered after the description field, before summary settings */
  afterDescription?: React.ReactNode

  /** Rendered at the very end of the form, after advanced settings */
  afterAdvanced?: React.ReactNode
}
```

### Registering Form Sections

External packages register form sections during app initialization:

```typescript
import { setCreateKbFormSections } from '@/features/knowledge/document/components'

setCreateKbFormSections({
  afterDescription: <AuthorizationSection />,
  afterAdvanced: <CustomFooter />,
})
```

### Post-Creation Hook

Register a handler to be called after KB creation (e.g., to set up external bindings):

```typescript
import { setPostCreateHandler } from '@/features/knowledge/document/components'

setPostCreateHandler(async (kbId) => {
  await myBindingApi.apply(kbId)
  await initializeExternalPermissions(kbId)
})
```

### Read/Write Separation

These extension points follow a **read/write separation** pattern:

| File | Write (External Package) | Read (Open-Source Component) |
|------|--------------------------|------------------------------|
| `createKbDialogState.ts` | `setCreateKbFormSections()` | `getCreateKbFormSections()` |
| `createKbDialogState.ts` | `setPostCreateHandler()` | `runPostCreateHandler()` |

## Role Select Extension

The `AddUserForm` component allows replacing the default role `<Select>` dropdown with a custom component.

### RoleSelectComponent Props

```typescript
export interface RoleSelectComponentProps {
  value: MemberRole
  onChange: (role: MemberRole) => void
}
```

### Registration

```typescript
import { setRoleSelectComponent } from '@/features/knowledge/permission/components'
import { ErpRoleSelect } from './ErpRoleSelect'

setRoleSelectComponent(ErpRoleSelect)
```

When registered, `AddUserForm` renders the custom component instead of the default role dropdown. This is useful for ERP integrations that need to display custom role options alongside standard ones.

### Clear

Pass `undefined` to clear the registered component:

```typescript
setRoleSelectComponent(undefined)
```

## Backend Integration

### Python Entry Points for Permission Resolvers

The backend uses Python entry points to dynamically load permission resolver implementations:

```toml
[project.entry-points."wegent.kb_permissions"]
department = "app.extensions.myext.kb_permissions:DepartmentPermissionResolver"
```

Implement the resolver interface:

```python
from app.services.readers.kb_permissions import IKbPermissionResolver

class DepartmentPermissionResolver(IKbPermissionResolver):
    def __init__(self, base: IKbPermissionResolver):
        self._base = base

    def resolve(self, db, kb_id, user_id, kb):
        if self._has_department_access(db, kb_id, user_id):
            return "Developer"
        return self._base.resolve(db, kb_id, user_id, kb)

    def get_accessible_kb_ids(self, db, user_id):
        dept_ids = self._get_dept_accessible_kbs(db, user_id)
        base_ids = self._base.get_accessible_kb_ids(db, user_id)
        return list(set(dept_ids + base_ids))
```

## Best Practices

1. **Initialize Early**: Call `registerComponents()`, `setExternalBindingApi()`, and other registration functions during application initialization (before any components are rendered).

2. **Lazy Component Resolution**: Use `useMemo(() => getComponent(name, Default), [])` at render time, not module-level `getComponent()` calls. This ensures registered components are available even with non-deterministic module import ordering.

3. **Unique IDs**: Ensure extension tab IDs and provider names are unique to avoid conflicts.

4. **Permission Checks**: Use `requiresManagePermission` appropriately to hide extension tabs from users without management rights.

5. **Error Boundaries**: Wrap extension components with error boundaries to prevent crashes from affecting the entire panel.

6. **Error Handling**: Always check `hasExternalBindingApi()` before accessing the binding API, or use `getExternalBindingApi(true)` to throw a descriptive error.

7. **Consistent Styling**: Use the project's design system components for consistent UI.

8. **i18n Support**: Use the `useTranslation` hook for all user-facing text in extension components.

## Extension Points Summary

| File | Export | Type | Description |
|------|--------|------|-------------|
| `registry.ts` | `registerComponents()` | Override | Replace DocumentPanel or KnowledgeDetailPanel entirely |
| `knowledgeExtensions.ts` | `setExternalBindingApi()` | Provider + Bridge | Set external binding API with searchable providers |
| `knowledgeExtensions.ts` | `bindingProviderRegistry` | Registry | Register/unregister binding providers |
| `knowledgeExtensions.ts` | `hasExternalBindingApi()` | Check | Check if binding API is available |
| `knowledgeExtensions.ts` | `getExternalBindingApi()` | Access | Get the binding API instance |
| `permission/components/KbPermissionsPanel.tsx` | `extensionTabs` prop | Prop Injection | Add custom permission management tabs |
| `document/components/createKbDialogState.ts` | `setCreateKbFormSections()` | State Bridge | Inject form sections into create KB dialog |
| `document/components/createKbDialogState.ts` | `setPostCreateHandler()` | State Bridge | Register post-creation hook |
| `permission/components/add-user-form-state.ts` | `setRoleSelectComponent()` | Component Bridge | Replace role select in AddUserForm |
| `document/components/index.ts` | Exports all above | N/A | Single import entry for all extension APIs |

## See Also

- [Permission System Concepts](../../concepts/permission-system.md)
- [Backend Extension Guide](../backend-extensions.md)
- [Component Design Guidelines](../component-design.md)
