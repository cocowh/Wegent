// SPDX-FileCopyrightText: 2025 Wegent, Inc.
//
// SPDX-License-Identifier: Apache-2.0

/**
 * Component registry for knowledge document components.
 *
 * This registry allows external packages (e.g., internal extensions) to
 * register custom implementations of knowledge document components without
 * modifying the open-source codebase.
 *
 * Usage (in external package):
 * ```typescript
 * import { registerComponents } from '@/features/knowledge/document/components';
 * import { CustomDocumentPanel } from './CustomDocumentPanel';
 *
 * registerComponents({
 *   DocumentPanel: CustomDocumentPanel,
 * });
 * ```
 */

import type { ComponentType, ReactNode } from 'react';
import type { DocumentPanelProps } from './DocumentPanel';
import type { KnowledgeDetailPanelProps } from './KnowledgeDetailPanel';
import type { KnowledgeBaseType } from '@/types/knowledge';

/**
 * Props for the CreateFormAuthorization component slot.
 *
 * This slot allows external packages to inject an authorization section
 * (e.g., user/department/role selection) into the knowledge base creation dialog.
 * The component manages its own internal state and communicates changes via the
 * onChange callback. Returned data is merged into the form's submit payload.
 */
export interface CreateFormAuthorizationProps {
  /** Current authorization data from the registered extension */
  value: Record<string, unknown>
  /** Called when authorization data changes, merged into submit payload on save */
  onChange: (data: Record<string, unknown>) => void
  /** Current KB type selected in the dialog (notebook or classic) */
  kbType: KnowledgeBaseType
  /** Child elements rendered below the authorization section */
  children?: ReactNode
}

/**
 * Registry of overridable knowledge document components.
 */
export interface ComponentRegistry {
  /** Document panel component for notebook KB right panel */
  DocumentPanel?: ComponentType<DocumentPanelProps>;
  /** Knowledge detail panel component for classic KB detail view */
  KnowledgeDetailPanel?: ComponentType<KnowledgeDetailPanelProps>;
  /**
   * Optional authorization section rendered in the knowledge base creation dialog.
   * When registered, this component is rendered between the description field and
   * summary settings. Its data is merged into the submit payload on form submission.
   */
  CreateFormAuthorization?: ComponentType<CreateFormAuthorizationProps>;
}

const registry: ComponentRegistry = {};

/**
 * Register component implementations.
 *
 * This function allows external packages to override default component
 * implementations. It should be called during application initialization,
 * before any components are rendered.
 *
 * @param components - Partial registry of components to register
 *
 * @example
 * ```typescript
 * import { registerComponents } from '@/features/knowledge/document/components';
 * import { CustomDocumentPanel } from '@internal/package';
 *
 * registerComponents({
 *   DocumentPanel: CustomDocumentPanel,
 * });
 * ```
 */
export function registerComponents(components: ComponentRegistry): void {
  Object.assign(registry, components);
}

/**
 * Get a registered component or return the default.
 *
 * @param name - Name of the component to get
 * @param defaultComponent - Default component to return if not registered
 * @returns The registered component or the default
 *
 * @example
 * ```typescript
 * const DocumentPanel = getComponent('DocumentPanel', DefaultDocumentPanel);
 * ```
 */
export function getComponent<K extends keyof ComponentRegistry>(
  name: K,
  defaultComponent: NonNullable<ComponentRegistry[K]>
): NonNullable<ComponentRegistry[K]> {
  return registry[name] || defaultComponent;
}

/**
 * Check if a component has been registered.
 *
 * @param name - Name of the component to check
 * @returns True if the component has been registered
 */
export function hasComponent<K extends keyof ComponentRegistry>(name: K): boolean {
  return name in registry && registry[name] !== undefined;
}

/**
 * Get a registered component without requiring a default fallback.
 *
 * Unlike `getComponent`, this function returns `undefined` when no component
 * has been registered for the given name. This is useful for optional slots
 * where the absence of a registered component means nothing is rendered.
 *
 * @param name - Name of the component to get
 * @returns The registered component or undefined if not registered
 *
 * @example
 * ```typescript
 * const AuthorizationComponent = getOptionalComponent('CreateFormAuthorization');
 * if (AuthorizationComponent) {
 *   return <AuthorizationComponent value={data} onChange={setData} kbType="notebook" />;
 * }
 * ```
 */
export function getOptionalComponent<K extends keyof ComponentRegistry>(
  name: K
): ComponentRegistry[K] {
  return registry[name];
}

/**
 * Clear all registered components.
 *
 * This is primarily useful for testing.
 */
export function clearRegistry(): void {
  Object.keys(registry).forEach((key) => {
    delete (registry as Record<string, unknown>)[key];
  });
}
