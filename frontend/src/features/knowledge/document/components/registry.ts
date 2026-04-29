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

import type { ComponentType } from 'react';
import type { DocumentPanelProps } from './DocumentPanel';
import type { KnowledgeDetailPanelProps } from './KnowledgeDetailPanel';

/**
 * Registry of overridable knowledge document components.
 */
export interface ComponentRegistry {
  /** Document panel component for notebook KB right panel */
  DocumentPanel?: ComponentType<DocumentPanelProps>;
  /** Knowledge detail panel component for classic KB detail view */
  KnowledgeDetailPanel?: ComponentType<KnowledgeDetailPanelProps>;
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
 * Clear all registered components.
 *
 * This is primarily useful for testing.
 */
export function clearRegistry(): void {
  Object.keys(registry).forEach((key) => {
    delete (registry as Record<string, unknown>)[key];
  });
}
