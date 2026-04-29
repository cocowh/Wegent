---
sidebar_position: 3
---

# 知识库扩展系统

本文档介绍知识库扩展系统，该系统提供多种扩展点用于集成外部系统（如 ERP、部门管理或自定义权限系统），而无需修改开源代码库。

## 概述

知识库扩展系统采用 **注册表 + 桥接** 模式：开源组件提供明确定义的扩展点，外部包在应用初始化期间注册其实现。这实现了开源代码与专有代码的清晰分离。

系统包含以下扩展机制：

| 扩展点 | 模式 | 描述 |
|--------|------|------|
| [组件注册表](#组件注册表) | 覆盖 | 替换整个组件（DocumentPanel、KnowledgeDetailPanel） |
| [外部绑定 API](#外部绑定-api) | 提供者 + 桥接 | 搜索、添加、删除和同步外部实体绑定 |
| [权限扩展标签页](#权限扩展标签页) | Props 注入 | 添加自定义权限管理标签页 |
| [创建知识库对话框扩展](#创建知识库对话框扩展) | 状态桥接 | 在明确定义的插槽位置注入表单区域 |
| [创建后钩子](#创建后钩子) | 状态桥接 | 在知识库创建后执行异步操作 |
| [自定义角色选择器](#角色选择器扩展) | 组件桥接 | 替换 AddUserForm 中的角色选择下拉框 |

## 组件注册表

组件注册表允许外部包在运行时覆盖整个知识文档组件。

### 注册表接口

```typescript
// frontend/src/features/knowledge/document/components/registry.ts

export interface ComponentRegistry {
  /** 笔记本 KB 右侧面板的文档面板组件 */
  DocumentPanel?: ComponentType<DocumentPanelProps>
  /** 经典 KB 详情视图的知识详情面板组件 */
  KnowledgeDetailPanel?: ComponentType<KnowledgeDetailPanelProps>
}
```

### 注册

在应用初始化期间、任何组件渲染之前调用 `registerComponents()`：

```typescript
import { registerComponents } from '@/features/knowledge/document/components'
import { CustomDocumentPanel } from './CustomDocumentPanel'

registerComponents({
  DocumentPanel: CustomDocumentPanel,
})
```

### 解析

开源组件使用 `getComponent()` 在 **渲染时**（而非模块加载时）解析已注册的组件，这为外部包提供了先填充注册表的时间：

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

### 工具函数

```typescript
/** 检查组件是否已注册 */
function hasComponent(name: keyof ComponentRegistry): boolean

/** 清除所有已注册组件（主要用于测试） */
function clearRegistry(): void
```

## 外部绑定 API

外部绑定 API 允许外部包将外部系统实体（部门、员工、客户等）绑定到知识库。

### 架构

绑定系统由两部分组成：

1. **绑定提供者注册表** — 声明可用的外部系统及其搜索能力
2. **外部绑定 API** — 提供绑定的 CRUD 操作

### 绑定提供者类型

```typescript
// frontend/src/apis/knowledgeExtensions.ts

export interface BindableItem {
  id: string
  name: string
  fullPath?: string    // 层级路径，例如 "部门 A / 团队 B"
  avatar?: string
  metadata?: Record<string, unknown>
}

export interface BindableTypeConfig {
  type: string           // 例如 'department'、'employee'、'customer'
  displayName: string
  icon?: string
  allowMultiple: boolean
}

export interface BindingProvider {
  name: string                   // 唯一标识符，例如 'erp'、'oa'
  displayName: string
  icon?: string
  searchable: boolean
  bindableTypes: BindableTypeConfig[]
  search: (keyword: string, type?: string) => Promise<BindingSearchResult>
  validate: (externalId: string, type: string) => Promise<boolean>
  getItemDetails?: (externalId: string, type: string) => Promise<BindableItem | null>
}
```

### 外部绑定数据模型

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

### 外部绑定 API 接口

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

### 使用方法

外部包在应用初始化期间注册提供者并设置 API 实现：

```typescript
import {
  bindingProviderRegistry,
  setExternalBindingApi,
  type BindingProvider,
} from '@/apis/knowledgeExtensions'

// 注册绑定提供者（例如 ERP 部门搜索）
bindingProviderRegistry.register({
  name: 'erp',
  displayName: 'ERP 系统',
  searchable: true,
  bindableTypes: [
    { type: 'department', displayName: '部门', allowMultiple: true },
  ],
  search: async (keyword, type) => {
    // 搜索 ERP API 获取部门/员工
    return { items: [...], hasMore: false }
  },
  validate: async (externalId, type) => {
    // 验证外部 ID
    return true
  },
})

// 设置绑定 API 实现
setExternalBindingApi({
  providers: bindingProviderRegistry,
  search: async (keyword, provider, type) => { /* ... */ },
  list: async (kbId, provider) => { /* ... */ },
  add: async (kbId, data) => { /* ... */ },
  remove: async (kbId, bindingId) => { /* ... */ },
  sync: async (kbId, bindingId) => { /* ... */ },
})
```

### 访问 API

开源组件安全地检查可用性并访问 API：

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

## 权限扩展标签页

`KbPermissionsPanel` 组件提供了 `extensionTabs` prop 用于在默认的个人权限标签页之外添加额外的权限管理标签页。

### ExtensionTabConfig 接口

```typescript
export interface ExtensionTabConfig {
  /** 标签页唯一标识符 */
  id: string
  /** 标签页显示标签 */
  label: string
  /** Lucide 图标组件 */
  icon: React.ComponentType<{ className?: string }>
  /** 标签页内容组件，接收 kbId 属性 */
  component: React.ComponentType<{ kbId: number }>
  /** 此标签页是否需要管理权限才可见 */
  requiresManagePermission?: boolean
}
```

### 使用方法

```typescript
import { Building2 } from 'lucide-react'
import { KbPermissionsPanel, type ExtensionTabConfig } from '@/features/knowledge/permission/components'

const departmentTab: ExtensionTabConfig = {
  id: 'department',
  label: '部门',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true,
}

// 在你的组件中：
<KbPermissionsPanel
  kbId={kbId}
  canManagePermissions={canManagePermissions}
  extensionTabs={[departmentTab]}
/>
```

`KnowledgeDetailPanel` 组件也通过 `permissionExtensionTabs` prop 暴露此功能：

```typescript
<KnowledgeDetailPanel
  selectedKb={selectedKb}
  permissionExtensionTabs={[departmentTab]}
/>
```

## 创建知识库对话框扩展

创建知识库对话框（`CreateKnowledgeBaseDialog`）提供了两种扩展机制：表单区域注入和创建后钩子。

### 表单区域

`KnowledgeBaseForm` 组件定义了明确定义的插槽位置，供外部包注入自定义 UI 区域：

```typescript
export interface KnowledgeBaseFormSections {
  /** 在描述字段之后、摘要设置之前渲染 */
  afterDescription?: React.ReactNode

  /** 在表单末尾、高级设置之后渲染 */
  afterAdvanced?: React.ReactNode
}
```

### 注册表单区域

外部包在应用初始化期间注册表单区域：

```typescript
import { setCreateKbFormSections } from '@/features/knowledge/document/components'

setCreateKbFormSections({
  afterDescription: <AuthorizationSection />,
  afterAdvanced: <CustomFooter />,
})
```

### 创建后钩子

注册一个在 KB 创建后调用的处理函数（例如，用于设置外部绑定）：

```typescript
import { setPostCreateHandler } from '@/features/knowledge/document/components'

setPostCreateHandler(async (kbId) => {
  await myBindingApi.apply(kbId)
  await initializeExternalPermissions(kbId)
})
```

### 读写分离

这些扩展点遵循 **读写分离** 模式：

| 文件 | 写（外部包） | 读（开源组件） |
|------|-------------|---------------|
| `createKbDialogState.ts` | `setCreateKbFormSections()` | `getCreateKbFormSections()` |
| `createKbDialogState.ts` | `setPostCreateHandler()` | `runPostCreateHandler()` |

## 角色选择器扩展

`AddUserForm` 组件允许使用自定义组件替换默认的角色 `<Select>` 下拉框。

### RoleSelectComponent Props

```typescript
export interface RoleSelectComponentProps {
  value: MemberRole
  onChange: (role: MemberRole) => void
}
```

### 注册

```typescript
import { setRoleSelectComponent } from '@/features/knowledge/permission/components'
import { ErpRoleSelect } from './ErpRoleSelect'

setRoleSelectComponent(ErpRoleSelect)
```

注册后，`AddUserForm` 将渲染自定义组件而不是默认的角色下拉框。这对于需要在标准角色选项旁边显示自定义角色选项的 ERP 集成非常有用。

### 清除

传递 `undefined` 以清除已注册的组件：

```typescript
setRoleSelectComponent(undefined)
```

## 后端集成

### 权限解析器的 Python Entry Points

后端使用 Python entry points 动态加载权限解析器实现：

```toml
[project.entry-points."wegent.kb_permissions"]
department = "app.extensions.myext.kb_permissions:DepartmentPermissionResolver"
```

实现解析器接口：

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

## 最佳实践

1. **尽早初始化**：在应用初始化期间（在任何组件渲染之前）调用 `registerComponents()`、`setExternalBindingApi()` 和其他注册函数。

2. **延迟组件解析**：在渲染时使用 `useMemo(() => getComponent(name, Default), [])`，而不是在模块级别调用 `getComponent()`。这确保即使模块导入顺序不确定，已注册的组件也可用。

3. **唯一 ID**：确保扩展标签页 ID 和提供者名称唯一，以避免冲突。

4. **权限检查**：适当使用 `requiresManagePermission` 向没有管理权限的用户隐藏扩展标签页。

5. **错误边界**：使用错误边界包装扩展组件，以防止崩溃影响整个面板。

6. **错误处理**：在访问绑定 API 之前始终检查 `hasExternalBindingApi()`，或使用 `getExternalBindingApi(true)` 抛出自描述性错误。

7. **一致的样式**：使用项目设计系统组件保持 UI 一致性。

8. **i18n 支持**：在扩展组件中使用 `useTranslation` 钩子处理所有面向用户的文本。

## 扩展点汇总

| 文件 | 导出 | 类型 | 描述 |
|------|------|------|------|
| `registry.ts` | `registerComponents()` | 覆盖 | 完全替换 DocumentPanel 或 KnowledgeDetailPanel |
| `knowledgeExtensions.ts` | `setExternalBindingApi()` | 提供者 + 桥接 | 设置具有可搜索提供者的外部绑定 API |
| `knowledgeExtensions.ts` | `bindingProviderRegistry` | 注册表 | 注册/注销绑定提供者 |
| `knowledgeExtensions.ts` | `hasExternalBindingApi()` | 检查 | 检查绑定 API 是否可用 |
| `knowledgeExtensions.ts` | `getExternalBindingApi()` | 访问 | 获取绑定 API 实例 |
| `permission/components/KbPermissionsPanel.tsx` | `extensionTabs` prop | Props 注入 | 添加自定义权限管理标签页 |
| `document/components/createKbDialogState.ts` | `setCreateKbFormSections()` | 状态桥接 | 向创建 KB 对话框注入表单区域 |
| `document/components/createKbDialogState.ts` | `setPostCreateHandler()` | 状态桥接 | 注册创建后钩子 |
| `permission/components/add-user-form-state.ts` | `setRoleSelectComponent()` | 组件桥接 | 替换 AddUserForm 中的角色选择器 |
| `document/components/index.ts` | 导出以上所有 | N/A | 所有扩展 API 的统一导入入口 |

## 另请参阅

- [权限系统概念](../../concepts/permission-system.md)
- [后端扩展指南](../backend-extensions.md)
- [组件设计指南](../component-design.md)
