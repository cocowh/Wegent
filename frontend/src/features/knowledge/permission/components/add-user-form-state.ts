// SPDX-FileCopyrightText: 2025 Wegent, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * Extension state for AddUserForm role select component.
 *
 * This module provides module-level state that allows external packages
 * to inject a custom role selector component without modifying the
 * open-source AddUserForm or its parent components.
 *
 * This follows the same pattern as `createKbDialogState.ts` (setCreateKbFormSections),
 * providing a read/write separation: open-source components read (get),
 * external packages write (set).
 *
 * Usage (in external package):
 * ```typescript
 * import { setRoleSelectComponent } from '@/features/knowledge/permission/components';
 * import { ErpRoleSelect } from './ErpRoleSelect';
 *
 * setRoleSelectComponent(ErpRoleSelect);
 * ```
 */

import type { ComponentType } from 'react'
import type { MemberRole } from '@/types/knowledge'

// ============== Types ==============

export interface RoleSelectComponentProps {
  /** Currently selected role value */
  value: MemberRole
  /** Role change callback */
  onChange: (role: MemberRole) => void
}

// ============== Role Select Component Bridge ==============

let _roleSelectComponent: ComponentType<RoleSelectComponentProps> | undefined

/**
 * Register a custom role select component for AddUserForm.
 * Called by external packages during app initialization.
 *
 * When registered, AddUserForm renders this component instead of the
 * default role `<Select>` dropdown. This is useful for ERP integrations
 * that need to display custom role options alongside standard ones.
 *
 * @param component - Custom role select component or undefined to clear
 */
export function setRoleSelectComponent(
  component: ComponentType<RoleSelectComponentProps> | undefined
): void {
  _roleSelectComponent = component
}

/**
 * Get the registered custom role select component.
 * Called by AddUserForm when rendering the role select field.
 *
 * @returns The registered component or undefined
 */
export function getRoleSelectComponent(): ComponentType<RoleSelectComponentProps> | undefined {
  return _roleSelectComponent
}
