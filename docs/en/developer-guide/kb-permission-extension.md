---
sidebar_position: 4
---

# Knowledge Base Extension System

This document describes the knowledge base extension system, which provides multiple extension points for integrating external systems (such as DingTalk, WeCom, ERP, or custom permission systems) without modifying the open-source codebase.

## Overview

The knowledge base extension system covers both **frontend** and **backend** layers, using a **registry + bridge** pattern: open-source components provide well-defined extension points, and external packages register their implementations during application initialization. This achieves clean separation between open-source and proprietary code.

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  External Package                   │
│                                                     │
│  ┌────────────────────┐  ┌────────────────────┐     │
│  │ Permission         │  │ Frontend           │     │
│  │ Resolver (Python)  │  │ Extensions (TS)    │     │
│  └─────────┬──────────┘  └─────────┬──────────┘     │
│            │                       │                │
└────────────┼───────────────────────┼────────────────┘
             │                       │
             ▼                       ▼
   ┌────────────────────┐  ┌────────────────────┐
   │  Backend Entry     │  │  Registry / State  │
   │  Points            │  │  Bridge Pattern    │
   │  wegent.kb_        │  │                    │
   │  permissions       │  │                    │
   └─────────┬──────────┘  └─────────┬──────────┘
             │                       │
             ▼                       ▼
   ┌─────────┬──────────┐  ┌─────────┬──────────┐
   │  Permission        │  │  UI Extension      │
   │  Resolution Chain  │  │  Points            │
   │  (Chain of Resp.)  │  │  (Props/Registry)  │
   └────────────────────┘  └────────────────────┘
```Frontend and backend extension points can be used independently or combined for complete end-to-end integration scenarios.

---

## Backend Extension: Permission Resolver

The backend uses Python entry points to dynamically load external permission resolvers, extending knowledge base access control.

### Permission Resolver Interface

```python
# backend/app/services/readers/kb_permissions.py

class IKbPermissionResolver(ABC):
    """
    Abstract interface for external knowledge base permission resolution.
    Implementations return a role string when the external system grants
    access, or None to fall through to built-in permission logic.
    """

    @abstractmethod
    def resolve(
        self,
        db: Session,
        kb_id: int,
        user_id: int,
        kb: object,
    ) -> Optional[str]:
        """
        Resolve permission for a single knowledge base access check.
        Called after all built-in checks have returned False.

        Returns:
            "Owner"/"Maintainer"/"Developer"/"Reporter" if the external
            system grants access, or None to continue with built-in denial.
        """
        pass

    @abstractmethod
    def get_accessible_kb_ids(self, db: Session, user_id: int) -> list[int]:
        """
        Return knowledge base IDs accessible to the user via external rules.
        Called during list queries to extend the OR conditions.

        Returns:
            List of knowledge base IDs (may be empty).
        """
        pass
```

### Registering an External Resolver

External packages declare entry points in `pyproject.toml`. The system loads them lazily on first use:

```toml
[project.entry-points."wegent.kb_permissions"]
department = "app.extensions.myext.kb_permissions:DepartmentPermissionResolver"
```

The resolver implementation uses the **decorator pattern**, receiving the base resolver instance so it can delegate back to built-in logic:

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

### Default Implementation

When no extension is configured, the no-op default implementation is used:

```python
class DefaultKbPermissionResolver(IKbPermissionResolver):
    def resolve(self, db, kb_id, user_id, kb) -> Optional[str]:
        return None  # No extra permissions granted

    def get_accessible_kb_ids(self, db, user_id) -> list[int]:
        return []  # No extra KBs added
```

### Loading Mechanism

The system uses `_LazyReader` for thread-safe lazy singleton loading:

```python
# Entry point is loaded on first use
# Falls back to DefaultKbPermissionResolver if not configured or loading fails
kb_permission_resolver: IKbPermissionResolver = _LazyReader()
```

### Permission Resolution Chain

The external resolver is called as the **last step** in the built-in permission check chain, ensuring it never interferes with built-in access control:

```
creator → ResourceMember → group → task binding → external resolver
```

- **resolve()**: Called at the end of `KnowledgeShareService.get_user_kb_permission()`, as the final opportunity after all built-in checks fail
- **get_accessible_kb_ids()**: Called in `KnowledgeService.list_knowledge_bases(scope=ALL)`, appending returned KB IDs to SQL OR conditions

### Error Isolation

Exceptions from the external resolver are caught during list queries to prevent a faulty extension from breaking the core listing functionality:

```python
try:
    ext_kb_ids = kb_permission_resolver.get_accessible_kb_ids(db, user_id)
except Exception as e:
    logger.warning(f"kb_permissions extension get_accessible_kb_ids failed: {e}")
    ext_kb_ids = []
```

---

## Frontend Extensions

The frontend provides multiple extension mechanisms covering component overrides, API injection, prop injection, and state bridge patterns.

### Component Registry

The component registry allows external packages to override core knowledge document components at runtime.

#### Registry Interface

```typescript
// frontend/src/features/knowledge/document/components/registry.ts

export interface ComponentRegistry {
  /** Document panel component for notebook KB right panel */
  DocumentPanel?: ComponentType<DocumentPanelProps>
  /** Knowledge detail panel component for classic KB detail view */
  KnowledgeDetailPanel?: ComponentType<KnowledgeDetailPanelProps>
}
```

#### Registration

Call `registerComponents()` during application initialization:

```typescript
import { registerComponents } from '@/features/knowledge/document/components'
import { CustomDocumentPanel } from './CustomDocumentPanel'

registerComponents({
  DocumentPanel: CustomDocumentPanel,
})
```

#### Resolution

Open-source components use `getComponent()` at **render time** (not at module load time):

```typescript
import { getComponent } from '@/features/knowledge/document/components'
import { DocumentPanel as DefaultDocumentPanel } from './DocumentPanel'

function DocumentPanel(props: DocumentPanelProps) {
  const Panel = useMemo(
    () => getComponent('DocumentPanel', DefaultDocumentPanel),
    []
  )
  return <Panel {...props} />
}
```

#### Utility Functions

```typescript
/** Check if a component has been registered */
function hasComponent(name: keyof ComponentRegistry): boolean

/** Clear all registered components (useful for testing) */
function clearRegistry(): void
```

### External Binding API

The external binding API allows external packages to bind external system entities (departments, employees, customers, etc.) to knowledge bases.

#### Binding Provider Types

```typescript
// frontend/src/apis/knowledgeExtensions.ts

export interface BindableItem {
  id: string
  name: string
  fullPath?: string    // Hierarchy path, e.g., "Dept A / Team B"
  avatar?: string
  metadata?: Record<string, unknown>
}

export interface BindingProvider {
  name: string                   // Unique identifier, e.g., 'erp', 'dingtalk'
  displayName: string
  icon?: string
  searchable: boolean
  bindableTypes: BindableTypeConfig[]
  search: (keyword: string, type?: string) => Promise<BindingSearchResult>
  validate: (externalId: string, type: string) => Promise<boolean>
  getItemDetails?: (externalId: string, type: string) => Promise<BindableItem | null>
}
```

#### Binding API Interface

```typescript
export interface ExternalBindingApi {
  readonly providers: BindingProviderRegistry

  search: (keyword: string, provider?: string, type?: string) =>
    Promise<Record<string, BindingSearchResult>>
  list: (kbId: number, provider?: string) => Promise<ExternalBinding[]>
  add: (kbId: number, data: ExternalBindingCreate) => Promise<ExternalBinding>
  remove: (kbId: number, bindingId: number) => Promise<void>
  sync: (kbId: number, bindingId: number) => Promise<void>
}
```

#### Registration and Usage

External packages set the API implementation during app initialization. Open-source components access it via safe getters:

```typescript
// Register provider + set API implementation
import { bindingProviderRegistry, setExternalBindingApi } from '@/apis/knowledgeExtensions'

bindingProviderRegistry.register({
  name: 'dingtalk',
  displayName: 'DingTalk',
  searchable: true,
  bindableTypes: [
    { type: 'department', displayName: 'Department', allowMultiple: true },
    { type: 'user', displayName: 'Employee', allowMultiple: false },
  ],
  search: async (keyword, type) => { /* call DingTalk API to search */ },
  validate: async (externalId, type) => { /* validate */ },
})

setExternalBindingApi({
  providers: bindingProviderRegistry,
  search: async (keyword, provider, type) => { /* ... */ },
  list: async (kbId, provider) => { /* ... */ },
  add: async (kbId, data) => { /* ... */ },
  remove: async (kbId, bindingId) => { /* ... */ },
  sync: async (kbId, bindingId) => { /* ... */ },
})

// Safe access by open-source components
import { hasExternalBindingApi, getExternalBindingApi } from '@/apis/knowledgeExtensions'

if (hasExternalBindingApi()) {
  const api = getExternalBindingApi()
  const bindings = await api.list(kbId)
}
```

### Permission Extension Tabs

The `KbPermissionsPanel` component provides an `extensionTabs` prop to add additional permission management tabs beyond the default personal permissions tab.

```typescript
export interface ExtensionTabConfig {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  component: React.ComponentType<{ kbId: number }>
  requiresManagePermission?: boolean
}
```

Usage example:

```typescript
import { Building2 } from 'lucide-react'
import { KbPermissionsPanel, type ExtensionTabConfig } from '@/features/knowledge/permission/components'

const departmentTab: ExtensionTabConfig = {
  id: 'department',
  label: 'Department Permissions',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true,
}

<KbPermissionsPanel
  kbId={kbId}
  canManagePermissions={canManagePermissions}
  extensionTabs={[departmentTab]}
/>
```

The `KnowledgeDetailPanel` also exposes this via the `permissionExtensionTabs` prop:

```typescript
<KnowledgeDetailPanel
  selectedKb={selectedKb}
  permissionExtensionTabs={[departmentTab]}
/>
```

### Create KB Dialog Extensions

The create KB dialog provides two extension mechanisms.

#### Form Section Injection

```typescript
export interface KnowledgeBaseFormSections {
  /** Rendered after the description field, before summary settings */
  afterDescription?: React.ReactNode
  /** Rendered at the end of the form, after advanced settings */
  afterAdvanced?: React.ReactNode
}
```

External packages register form sections:

```typescript
import { setCreateKbFormSections } from '@/features/knowledge/document/components'

setCreateKbFormSections({
  afterDescription: <AuthorizationSection />,
})
```

#### Post-Creation Hook

```typescript
import { setPostCreateHandler } from '@/features/knowledge/document/components'

setPostCreateHandler(async (kbId) => {
  await initializeExternalPermissions(kbId)
})
```

### Role Select Extension

The `AddUserForm` allows replacing the default role dropdown with a custom component:

```typescript
import { setRoleSelectComponent } from '@/features/knowledge/permission/components'
import { ErpRoleSelect } from './ErpRoleSelect'

setRoleSelectComponent(ErpRoleSelect)

// Pass undefined to clear the registered component
setRoleSelectComponent(undefined)
```

---

## End-to-End Example: Integrating DingTalk Organization

This example demonstrates how to combine frontend and backend extension points to integrate DingTalk's organizational structure into the KB permission system.

### Scenario

An enterprise uses DingTalk as its organization management system and wants to:
1. Automatically grant KB access based on DingTalk department membership (backend)
2. Search and bind DingTalk departments/employees in the permission management UI (frontend)
3. Associate DingTalk approval scope when creating a KB (frontend form extension)

### Step 1: Backend Permission Resolver

Create a DingTalk department permission resolver that verifies user department membership through the DingTalk Open API.

```python
# myext/kb_permissions.py
from typing import Optional
from sqlalchemy.orm import Session
from app.services.readers.kb_permissions import IKbPermissionResolver

class DingTalkPermissionResolver(IKbPermissionResolver):
    """Resolves KB permissions based on DingTalk department membership."""

    def __init__(self, base: IKbPermissionResolver):
        self._base = base
        self._client = self._init_dingtalk_client()

    def _init_dingtalk_client(self):
        """Initialize DingTalk Open Platform client."""
        import dingtalk
        return dingtalk.Client(
            app_key=os.environ["DINGTALK_APP_KEY"],
            app_secret=os.environ["DINGTALK_APP_SECRET"],
        )

    def _get_user_dept_ids(self, user_id: int) -> list[str]:
        """Get DingTalk department IDs for a Wegent user. Requires user mapping."""
        return []

    def _get_kb_bound_dept_ids(self, kb_id: int) -> list[str]:
        """Get DingTalk department IDs bound to a KB."""
        return []

    def resolve(self, db, kb_id, user_id, kb) -> Optional[str]:
        user_dept_ids = self._get_user_dept_ids(user_id)
        bound_dept_ids = self._get_kb_bound_dept_ids(kb_id)

        # Grant Developer role if user's departments overlap with KB-bound departments
        if set(user_dept_ids) & set(bound_dept_ids):
            return "Developer"

        return self._base.resolve(db, kb_id, user_id, kb)

    def get_accessible_kb_ids(self, db, user_id) -> list[int]:
        user_dept_ids = self._get_user_dept_ids(user_id)
        if not user_dept_ids:
            return self._base.get_accessible_kb_ids(db, user_id)

        # Query all KB IDs bound to the user's departments
        kb_ids = self._query_bound_kb_ids(db, user_dept_ids)

        # Merge with built-in results
        base_ids = self._base.get_accessible_kb_ids(db, user_id)
        return list(set(kb_ids + base_ids))

    def _query_bound_kb_ids(self, db, dept_ids: list[str]) -> list[int]:
        """Query all KB IDs bound to the given DingTalk department IDs."""
        return []
```

Register in `pyproject.toml`:

```toml
[project.entry-points."wegent.kb_permissions"]
dingtalk = "myext.kb_permissions:DingTalkPermissionResolver"
```

### Step 2: Frontend Binding Provider

Register a DingTalk binding provider on the frontend to enable department/employee search.

```typescript
// myext/dingtalk-binding.ts
import {
  bindingProviderRegistry,
  setExternalBindingApi,
  type BindingProvider,
  type ExternalBindingApi,
  type ExternalBinding,
  type ExternalBindingCreate,
  type BindingSearchResult,
} from '@/apis/knowledgeExtensions'

// Register DingTalk binding provider
bindingProviderRegistry.register({
  name: 'dingtalk',
  displayName: 'DingTalk',
  searchable: true,
  bindableTypes: [
    { type: 'department', displayName: 'Department', icon: 'building2', allowMultiple: true },
    { type: 'user', displayName: 'Employee', icon: 'user', allowMultiple: false },
  ],
  search: async (keyword: string, type?: string): Promise<BindingSearchResult> => {
    const response = await fetch(`/api/ext/dingtalk/search?keyword=${keyword}&type=${type || ''}`)
    return response.json()
  },
  validate: async (externalId: string, type: string): Promise<boolean> => {
    const response = await fetch(`/api/ext/dingtalk/validate?id=${externalId}&type=${type}`)
    return response.ok
  },
})

// Set binding API implementation
class DingTalkBindingApi implements ExternalBindingApi {
  providers = bindingProviderRegistry

  async search(keyword: string, provider?: string, type?: string) {
    const results: Record<string, BindingSearchResult> = {}
    const providers = provider
      ? [this.providers.get(provider)!].filter(Boolean)
      : this.providers.getAll()

    for (const p of providers) {
      if (p.searchable) {
        results[p.name] = await p.search(keyword, type)
      }
    }
    return results
  }

  async list(kbId: number, provider?: string): Promise<ExternalBinding[]> {
    const response = await fetch(`/api/ext/dingtalk/bindings?kbId=${kbId}`)
    return response.json()
  }

  async add(kbId: number, data: ExternalBindingCreate): Promise<ExternalBinding> {
    const response = await fetch(`/api/ext/dingtalk/bindings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kbId, ...data }),
    })
    return response.json()
  }

  async remove(kbId: number, bindingId: number): Promise<void> {
    await fetch(`/api/ext/dingtalk/bindings/${bindingId}?kbId=${kbId}`, { method: 'DELETE' })
  }

  async sync(kbId: number, bindingId: number): Promise<void> {
    await fetch(`/api/ext/dingtalk/bindings/${bindingId}/sync?kbId=${kbId}`, { method: 'POST' })
  }
}

setExternalBindingApi(new DingTalkBindingApi())
```

### Step 3: Frontend Permission Extension Tab

Create a DingTalk department permission tab to display and manage bound DingTalk departments for the current KB.

```typescript
// myext/DingTalkPermissionTab.tsx
import { useState, useEffect } from 'react'
import { getExternalBindingApi } from '@/apis/knowledgeExtensions'

export function DingTalkPermissionTab({ kbId }: { kbId: number }) {
  const api = getExternalBindingApi()
  const [bindings, setBindings] = useState<ExternalBinding[]>([])
  const [searchResults, setSearchResults] = useState<BindingSearchResult | null>(null)

  useEffect(() => {
    api?.list(kbId).then(setBindings)
  }, [kbId])

  const handleSearch = async (keyword: string) => {
    const results = await api?.search(keyword, 'dingtalk', 'department')
    if (results) setSearchResults(results['dingtalk'] || null)
  }

  const handleAdd = async (externalId: string) => {
    await api?.add(kbId, { provider: 'dingtalk', bindableType: 'department', externalId })
    const updated = await api?.list(kbId)
    setBindings(updated || [])
  }

  const handleRemove = async (bindingId: number) => {
    await api?.remove(kbId, bindingId)
    setBindings(bindings.filter(b => b.id !== bindingId))
  }

  return (
    <div className="space-y-4">
      <h3>DingTalk Department Permissions</h3>

      <input
        placeholder="Search DingTalk departments..."
        onChange={e => handleSearch(e.target.value)}
        data-testid="dingtalk-dept-search"
      />

      {searchResults?.items.map(item => (
        <div key={item.id}>
          <span>{item.name}</span>
          <button onClick={() => handleAdd(item.id)}>Add</button>
        </div>
      ))}

      <h4>Bound Departments</h4>
      {bindings.filter(b => b.provider === 'dingtalk').map(binding => (
        <div key={binding.id}>
          <span>{binding.name}</span>
          <button onClick={() => handleRemove(binding.id)}>Remove</button>
        </div>
      ))}
    </div>
  )
}
```

Inject into the permission panel:

```typescript
import { DingTalkPermissionTab } from './DingTalkPermissionTab'

const dingtalkTab: ExtensionTabConfig = {
  id: 'dingtalk-department',
  label: 'DingTalk Departments',
  icon: Building2,
  component: DingTalkPermissionTab,
  requiresManagePermission: true,
}

<KbPermissionsPanel
  kbId={kbId}
  canManagePermissions={canManagePermissions}
  extensionTabs={[dingtalkTab]}
/>
```

### Step 4: Associate DingTalk Departments at KB Creation

Use form section injection to add a DingTalk department selector in the create KB dialog.

```typescript
// myext/DingTalkDeptSelector.tsx
export function DingTalkDeptSelector() {
  return (
    <div className="space-y-2">
      <label>Link DingTalk Departments</label>
      {/* Department selection UI */}
      <p className="text-xs text-text-muted">
        Members of selected departments will automatically gain access to this knowledge base
      </p>
    </div>
  )
}
```

Register form sections and post-creation hook:

```typescript
import { setCreateKbFormSections, setPostCreateHandler } from '@/features/knowledge/document/components'

// Inject form section
setCreateKbFormSections({
  afterDescription: <DingTalkDeptSelector />,
})

// Post-creation hook: auto-bind selected DingTalk departments
setPostCreateHandler(async (kbId) => {
  const selectedDeptIds = getSelectedDeptIds()
  const api = getExternalBindingApi()

  for (const deptId of selectedDeptIds) {
    await api?.add(kbId, {
      provider: 'dingtalk',
      bindableType: 'department',
      externalId: deptId,
    })
  }
})
```

---

## Extension Points Summary

| Layer | File | Interface | Pattern | Description |
|-------|------|-----------|---------|-------------|
| Backend | `kb_permissions.py` | `IKbPermissionResolver` | Entry Points + Decorator | Extend KB access permission resolution |
| Frontend | `registry.ts` | `registerComponents()` | Override | Replace DocumentPanel or KnowledgeDetailPanel entirely |
| Frontend | `knowledgeExtensions.ts` | `setExternalBindingApi()` | Provider + Bridge | Set external binding API with searchable providers |
| Frontend | `knowledgeExtensions.ts` | `bindingProviderRegistry` | Registry | Register/unregister binding providers |
| Frontend | `knowledgeExtensions.ts` | `hasExternalBindingApi()` | Check | Check if binding API is available |
| Frontend | `knowledgeExtensions.ts` | `getExternalBindingApi()` | Access | Get the binding API instance |
| Frontend | `KbPermissionsPanel.tsx` | `extensionTabs` prop | Prop Injection | Add custom permission management tabs |
| Frontend | `createKbDialogState.ts` | `setCreateKbFormSections()` | State Bridge | Inject form sections into create KB dialog |
| Frontend | `createKbDialogState.ts` | `setPostCreateHandler()` | State Bridge | Register post-creation hook |
| Frontend | `add-user-form-state.ts` | `setRoleSelectComponent()` | Component Bridge | Replace role select in AddUserForm |

## Best Practices

1. **Initialize Early**: Call `registerComponents()`, `setExternalBindingApi()`, and other registration functions during application initialization (before any components are rendered).

2. **Lazy Component Resolution**: Use `useMemo(() => getComponent(name, Default), [])` at render time, not module-level `getComponent()` calls. This ensures registered components are available even with non-deterministic module import ordering.

3. **Unique Identifiers**: Ensure extension tab IDs and provider names are unique to avoid conflicts.

4. **Permission Checks**: Use `requiresManagePermission` appropriately to hide extension tabs from users without management rights.

5. **Error Boundaries**: Wrap extension components with error boundaries to prevent crashes from affecting the entire panel.

6. **Error Handling**: Always check `hasExternalBindingApi()` before accessing the binding API, or use `getExternalBindingApi(true)` to throw a descriptive error. Backend list queries already isolate exceptions.

7. **Consistent Styling**: Use the project's design system components for consistent UI.

8. **i18n Support**: Use the `useTranslation` hook for all user-facing text in extension components.

9. **Backend Exception Isolation**: Permission resolvers should handle exceptions gracefully. The system automatically catches exceptions from external resolvers during list queries.
