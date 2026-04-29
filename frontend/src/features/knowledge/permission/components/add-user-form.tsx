// SPDX-FileCopyrightText: 2025 Weibo, Inc.
//
// SPDX-License-Identifier: Apache-2.0

'use client'

import { FormEvent } from 'react'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useTranslation } from '@/hooks/useTranslation'
import { UserSearchSelect } from '@/components/common/UserSearchSelect'
import type { MemberRole } from '@/types/knowledge'
import type { SearchUser } from '@/types/api'
import { getRoleSelectComponent } from './add-user-form-state'

interface AddUserFormProps {
  selectedUsers: SearchUser[]
  role: MemberRole
  onSelectedUsersChange: (users: SearchUser[]) => void
  onRoleChange: (role: MemberRole) => void
  onSubmit: (e: FormEvent) => void
  error: string | null
}

export function AddUserForm({
  selectedUsers,
  role,
  onSelectedUsersChange,
  onRoleChange,
  onSubmit,
  error,
}: AddUserFormProps) {
  const { t } = useTranslation('knowledge')
  const RoleSelectComponent = getRoleSelectComponent()

  return (
    <form onSubmit={onSubmit}>
      <div className="space-y-4 py-4">
        {/* User Search Select */}
        <div className="space-y-2">
          <Label>{t('document.permission.userName')}</Label>
          <UserSearchSelect
            selectedUsers={selectedUsers}
            onSelectedUsersChange={onSelectedUsersChange}
            placeholder={t('document.permission.searchUserPlaceholder')}
            multiple={true}
          />
        </div>

        {/* Role Select — use custom component if registered, otherwise default dropdown */}
        <div className="space-y-2">
          <Label htmlFor="role">{t('document.permission.role.label')}</Label>
          {RoleSelectComponent ? (
            <RoleSelectComponent value={role} onChange={onRoleChange} />
          ) : (
            <Select value={role} onValueChange={v => onRoleChange(v as MemberRole)}>
              <SelectTrigger id="role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Maintainer">
                  <div>
                    <div className="font-medium">{t('document.permission.role.Maintainer')}</div>
                    <div className="text-xs text-text-muted">
                      {t('document.permission.role.MaintainerDescription')}
                    </div>
                  </div>
                </SelectItem>
                <SelectItem value="Developer">
                  <div>
                    <div className="font-medium">{t('document.permission.role.Developer')}</div>
                    <div className="text-xs text-text-muted">
                      {t('document.permission.role.DeveloperDescription')}
                    </div>
                  </div>
                </SelectItem>
                <SelectItem value="Reporter">
                  <div>
                    <div className="font-medium">{t('document.permission.role.Reporter')}</div>
                    <div className="text-xs text-text-muted">
                      {t('document.permission.role.ReporterDescription')}
                    </div>
                  </div>
                </SelectItem>
                <SelectItem value="RestrictedAnalyst">
                  <div>
                    <div className="font-medium">
                      {t('document.permission.role.RestrictedAnalyst')}
                    </div>
                    <div className="text-xs text-text-muted">
                      {t('document.permission.role.RestrictedAnalystDescription')}
                    </div>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="text-sm text-error bg-error/10 px-3 py-2 rounded-lg">{error}</div>
        )}
      </div>
    </form>
  )
}
