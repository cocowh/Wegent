// SPDX-FileCopyrightText: 2025 Wegent, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * Extension point for knowledge-related APIs.
 *
 * This module allows external packages to register additional API functions
 * that can be used by knowledge components without modifying the open-source
 * codebase.
 *
 * Usage (in external package):
 * ```typescript
 * import { knowledgeApiExtensions } from '@/apis/knowledgeExtensions';
 *
 * knowledgeApiExtensions.erpBindingApi = {
 *   add: async (kbId, data) => { ... },
 *   remove: async (kbId, bindingId) => { ... },
 *   list: async (kbId) => { ... },
 * };
 * ```
 */

/**
 * Interface for ERP binding API operations.
 * This is an example of how external APIs can be typed.
 */
export interface ErpBindingApi {
  /** Add an ERP binding to a knowledge base */
  add: (kbId: number, data: unknown) => Promise<unknown>;
  /** Remove an ERP binding from a knowledge base */
  remove: (kbId: number, bindingId: number) => Promise<void>;
  /** List ERP bindings for a knowledge base */
  list: (kbId: number) => Promise<unknown[]>;
}

/**
 * Registry of extended knowledge APIs.
 */
export interface KnowledgeApiExtensions {
  /** ERP department/employee binding API */
  erpBindingApi?: ErpBindingApi;
}

/**
 * Global registry for knowledge API extensions.
 *
 * External packages can add their API implementations to this object
 * during application initialization.
 */
export const knowledgeApiExtensions: KnowledgeApiExtensions = {};

/**
 * Check if an ERP binding API is available.
 *
 * @returns True if the ERP binding API has been registered
 */
export function hasErpBindingApi(): boolean {
  return knowledgeApiExtensions.erpBindingApi !== undefined;
}

/**
 * Get the ERP binding API if available.
 *
 * @returns The ERP binding API or undefined if not registered
 * @throws Error if the API is not available and throwIfMissing is true
 */
export function getErpBindingApi(throwIfMissing = false): ErpBindingApi | undefined {
  const api = knowledgeApiExtensions.erpBindingApi;
  if (throwIfMissing && !api) {
    throw new Error('ERP binding API is not available. Ensure the ERP extension is registered.');
  }
  return api;
}
