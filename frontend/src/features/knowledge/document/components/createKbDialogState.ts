// SPDX-FileCopyrightText: 2025 Wegent, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * Extension state for CreateKnowledgeBaseDialog.
 *
 * This module provides module-level state bridges that allow external packages
 * to inject form sections and register post-creation hooks without modifying
 * the open-source page component.
 *
 * This follows the same pattern as `knowledgeExtensions.ts` (setExternalBindingApi),
 * providing a read/write separation: open-source components read (get/run),
 * external packages write (set/register).
 *
 * Usage (in external package):
 * ```typescript
 * import {
 *   setCreateKbFormSections,
 *   setPostCreateHandler,
 * } from '@/features/knowledge/document/components/createKbDialogState';
 *
 * // Inject custom form sections
 * setCreateKbFormSections({
 *   afterDescription: <MyAuthSection />,
 * });
 *
 * // Register post-creation hook
 * setPostCreateHandler(async (kbId) => {
 *   await myBindingApi.apply(kbId);
 * });
 * ```
 */

import type { KnowledgeBaseFormSections } from './KnowledgeBaseForm'

// ============== Form Sections Bridge ==============

let _formSections: KnowledgeBaseFormSections | undefined

/**
 * Set the form sections to be injected into CreateKnowledgeBaseDialog.
 * Called by external packages during app initialization.
 *
 * @param sections - Form sections or undefined to clear
 */
export function setCreateKbFormSections(
  sections: KnowledgeBaseFormSections | undefined
): void {
  _formSections = sections
}

/**
 * Get the registered form sections for CreateKnowledgeBaseDialog.
 * Called by open-source page component when rendering the dialog.
 *
 * @returns The registered form sections or undefined
 */
export function getCreateKbFormSections(): KnowledgeBaseFormSections | undefined {
  return _formSections
}

// ============== Post-Creation Hook ==============

let _postCreateHandler: ((kbId: number) => Promise<void>) | undefined

/**
 * Register a handler to be called after a knowledge base is created.
 * The handler receives the created KB's ID.
 *
 * @param handler - Async handler or undefined to clear
 */
export function setPostCreateHandler(
  handler: ((kbId: number) => Promise<void>) | undefined
): void {
  _postCreateHandler = handler
}

/**
 * Run the registered post-creation handler with the given KB ID.
 * Called by open-source page component after successful KB creation.
 *
 * @param kbId - The created knowledge base ID
 */
export async function runPostCreateHandler(kbId: number): Promise<void> {
  if (_postCreateHandler) {
    await _postCreateHandler(kbId)
  }
}
