---
sidebar_position: 3
---

# 知识库权限扩展

本文档介绍如何通过自定义权限标签页扩展知识库权限系统，例如通过外部 ERP 系统实现部门级权限管理。

## 概述

知识库权限系统提供了一个扩展点，允许您在默认的个人权限标签页之外添加额外的权限管理标签页。这对于集成外部权限系统（如 ERP 或企业身份管理系统）非常有用。

## 扩展点

扩展通过 `ExtensionTabConfig` 接口和 `KbPermissionsPanel` 组件实现。

### ExtensionTabConfig 接口

```typescript
interface ExtensionTabConfig {
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

### 基本用法

要添加自定义权限标签页，请包装 `KnowledgeDetailPanel` 组件并注入您的扩展标签页：

```typescript
'use client'

import { Building2 } from 'lucide-react'
import { KnowledgeDetailPanel, type ExtensionTabConfig } from '@/features/knowledge'

// 您的自定义权限管理组件
function DepartmentPermissionTab({ kbId }: { kbId: number }) {
  // 在此实现部门权限 UI
  return <div>知识库 {kbId} 的部门权限</div>
}

// 定义扩展标签页
const departmentExtensionTab: ExtensionTabConfig = {
  id: 'department',
  label: '部门',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true,
}

// 扩展的知识库详情面板
interface ExtendedKnowledgeDetailPanelProps {
  selectedKb: KnowledgeBase | null
  // ... 其他属性
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

## 实现指南

### 第一步：创建权限组件

创建一个实现自定义权限逻辑的组件：

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
    // 获取此知识库的部门权限
    fetchDepartmentPermissions(kbId).then(setPermissions)
  }, [kbId])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium">部门权限</h3>
        <Button>添加部门</Button>
      </div>
      {/* 渲染权限管理 UI */}
      {permissions.map(dept => (
        <Card key={dept.id}>{dept.name}</Card>
      ))}
    </div>
  )
}
```

### 第二步：配置扩展标签页

定义您的扩展标签页配置：

```typescript
import { Building2 } from 'lucide-react'
import type { ExtensionTabConfig } from '@/features/knowledge'
import { DepartmentPermissionTab } from './DepartmentPermissionTab'

export const departmentExtensionTab: ExtensionTabConfig = {
  id: 'department',
  label: '部门',
  icon: Building2,
  component: DepartmentPermissionTab,
  requiresManagePermission: true, // 仅对具有管理权限的用户显示
}
```

### 第三步：注入 KnowledgeDetailPanel

包装 `KnowledgeDetailPanel` 以注入您的扩展：

```typescript
// features/knowledge/extensions/ExtendedKnowledgeDetailPanel.tsx
import { KnowledgeDetailPanel, type ExtensionTabConfig } from '@/features/knowledge'
import { departmentExtensionTab } from './departmentExtensionTab'

interface ExtendedKnowledgeDetailPanelProps {
  selectedKb: KnowledgeBase | null
  // ... KnowledgeDetailPanelProps 的其他属性
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

## 后端集成

您的自定义权限标签页应通过 `IKbPermissionResolver` 接口与后端集成。详情请参阅[后端文档](../../concepts/permission-system.md)。

### API 端点

您应该为自定义权限系统创建以下 API 端点：

- `GET /api/knowledge-bases/{kb_id}/department-permissions` - 列出部门权限
- `POST /api/knowledge-bases/{kb_id}/department-permissions` - 添加部门权限
- `DELETE /api/knowledge-bases/{kb_id}/department-permissions/{id}` - 移除部门权限

### 后端扩展

在后端实现 `IKbPermissionResolver` 接口：

```python
# backend/app/extensions/myext/kb_permissions.py
from app.services.readers.kb_permissions import IKbPermissionResolver

class DepartmentPermissionResolver(IKbPermissionResolver):
    def resolve(self, db, kb_id, user_id, kb):
        # 检查用户是否通过部门拥有访问权限
        if self._has_department_access(db, kb_id, user_id):
            return "Developer"
        return None

    def get_accessible_kb_ids(self, db, user_id):
        # 返回通过部门可访问的 KB ID
        return self._get_dept_accessible_kbs(db, user_id)

def wrap(base: IKbPermissionResolver) -> DepartmentPermissionResolver:
    return DepartmentPermissionResolver()
```

通过环境变量配置扩展：

```bash
SERVICE_EXTENSION=app.extensions.myext
```

## 示例

### ERP 部门权限

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
      {/* 授权部门列表 */}
    </div>
  )
}

export const erpExtensionTab: ExtensionTabConfig = {
  id: 'department',
  label: '部门',
  icon: Building2,
  component: ErpDeptTab,
  requiresManagePermission: true,
}
```

### 多个扩展标签页

您可以添加多个扩展标签页：

```typescript
const extensionTabs: ExtensionTabConfig[] = [
  {
    id: 'department',
    label: '部门',
    icon: Building2,
    component: DepartmentTab,
    requiresManagePermission: true,
  },
  {
    id: 'employee',
    label: '员工',
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

## 最佳实践

1. **唯一 ID**：确保您的扩展标签页 ID 唯一以避免冲突。

2. **权限检查**：适当使用 `requiresManagePermission` 向没有管理权限的用户隐藏标签页。

3. **懒加载**：对于较重的组件，使用动态导入：

   ```typescript
   const DepartmentTab = lazy(() => import('./DepartmentTab'))
   ```

4. **错误边界**：使用错误边界包装您的扩展组件，以防止崩溃影响整个面板。

5. **一致的样式**：使用项目的设计系统组件（Card、Button 等）以保持 UI 一致。

6. **i18n 支持**：使用 `useTranslation` 钩子处理所有面向用户的文本。

## 故障排除

### 扩展标签页不显示

- 检查标签页 ID 是否唯一
- 验证 `requiresManagePermission` 逻辑（如适用）
- 确保组件正确导出和导入

### 权限未应用

- 验证后端 `IKbPermissionResolver` 实现
- 检查 `SERVICE_EXTENSION` 环境变量是否已设置
- 查看后端日志中的扩展加载错误

### 类型错误

- 确保 `ExtensionTabConfig` 从正确的位置导入
- 验证组件属性类型匹配 `{ kbId: number }`

## 另请参阅

- [权限系统概念](../../concepts/permission-system.md)
- [后端扩展指南](../backend-extensions.md)
- [组件设计指南](../component-design.md)
