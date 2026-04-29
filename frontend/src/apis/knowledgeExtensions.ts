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
 * import {
 *   bindingProviderRegistry,
 *   setExternalBindingApi,
 *   type BindingProvider,
 * } from '@/apis/knowledgeExtensions';
 *
 * // Register a binding provider (e.g., ERP department search)
 * bindingProviderRegistry.register({
 *   name: 'erp',
 *   displayName: 'ERP System',
 *   searchable: true,
 *   bindableTypes: [{ type: 'department', displayName: 'Department', allowMultiple: true }],
 *   search: async (keyword, type) => { ... },
 *   validate: async (externalId, type) => { ... },
 * });
 *
 * // Set the binding API implementation
 * setExternalBindingApi({
 *   providers: bindingProviderRegistry,
 *   search: async (keyword, provider, type) => { ... },
 *   list: async (kbId, provider) => { ... },
 *   add: async (kbId, data) => { ... },
 *   remove: async (kbId, bindingId) => { ... },
 *   sync: async (kbId, bindingId) => { ... },
 * });
 * ```
 */

// ============== Binding Provider Types ==============

/**
 * Represents an item that can be bound to a knowledge base
 */
export interface BindableItem {
  /** External system ID */
  id: string
  /** Display name */
  name: string
  /** Full path/name hierarchy (e.g., "Dept A / Team B") */
  fullPath?: string
  /** Avatar or icon URL */
  avatar?: string
  /** Additional metadata from external system */
  metadata?: Record<string, unknown>
}

/**
 * Result of searching bindable items
 */
export interface BindingSearchResult {
  items: BindableItem[]
  /** Whether more results are available */
  hasMore: boolean
  /** Total count if available */
  total?: number
}

/**
 * Configuration for a bindable type
 */
export interface BindableTypeConfig {
  /** Type identifier, e.g., 'department', 'employee', 'customer' */
  type: string
  /** Display name, e.g., 'Department', 'Employee' */
  displayName: string
  /** Icon identifier */
  icon?: string
  /** Whether multiple items of this type can be bound */
  allowMultiple: boolean
}

/**
 * A binding provider represents an external system that can bind
 * its entities (departments, employees, etc.) to knowledge bases.
 */
export interface BindingProvider {
  /** Unique provider identifier, e.g., 'erp', 'oa', 'crm' */
  name: string

  /** Human-readable display name */
  displayName: string

  /** Optional icon URL or identifier */
  icon?: string

  /** Whether this provider supports search functionality */
  searchable: boolean

  /** Available bindable types from this provider */
  bindableTypes: BindableTypeConfig[]

  /**
   * Search for bindable items in the external system
   * @param keyword - Search keyword
   * @param type - Optional type filter
   * @returns Search results with items
   */
  search: (keyword: string, type?: string) => Promise<BindingSearchResult>

  /**
   * Validate if an external ID is valid and can be bound
   * @param externalId - The external system ID
   * @param type - The bindable type
   * @returns Whether the binding is valid
   */
  validate: (externalId: string, type: string) => Promise<boolean>

  /**
   * Get item details by ID
   * @param externalId - The external system ID
   * @param type - The bindable type
   * @returns Item details or null if not found
   */
  getItemDetails?: (externalId: string, type: string) => Promise<BindableItem | null>
}

// ============== Binding Types ==============

/**
 * Represents a binding between a knowledge base and an external entity
 */
export interface ExternalBinding {
  /** Binding ID */
  id: number
  /** Knowledge base ID */
  kbId: number
  /** Provider name */
  provider: string
  /** Bindable type */
  bindableType: string
  /** External system ID */
  externalId: string
  /** Display name */
  name: string
  /** Full path from external system */
  fullPath?: string
  /** Avatar URL */
  avatar?: string
  /** Additional metadata */
  metadata?: Record<string, unknown>
  /** Creation timestamp */
  createdAt: string
}

/**
 * Data required to create a new binding
 */
export interface ExternalBindingCreate {
  provider: string
  bindableType: string
  externalId: string
}

// ============== Extension Registry ==============

/**
 * Registry of binding providers
 */
class BindingProviderRegistry {
  private providers: Map<string, BindingProvider> = new Map()

  /**
   * Register a new binding provider
   * @param provider - The provider to register
   * @throws Error if provider with same name already exists
   */
  register(provider: BindingProvider): void {
    if (this.providers.has(provider.name)) {
      throw new Error(`Binding provider '${provider.name}' is already registered`)
    }
    this.providers.set(provider.name, provider)
  }

  /**
   * Unregister a binding provider
   * @param name - Provider name
   * @returns True if provider was removed
   */
  unregister(name: string): boolean {
    return this.providers.delete(name)
  }

  /**
   * Get a specific provider
   * @param name - Provider name
   * @returns The provider or undefined
   */
  get(name: string): BindingProvider | undefined {
    return this.providers.get(name)
  }

  /**
   * Get all registered providers
   * @returns Array of all providers
   */
  getAll(): BindingProvider[] {
    return Array.from(this.providers.values())
  }

  /**
   * Check if a provider is registered
   * @param name - Provider name
   * @returns True if provider exists
   */
  has(name: string): boolean {
    return this.providers.has(name)
  }

  /**
   * Get total number of registered providers
   */
  get size(): number {
    return this.providers.size
  }
}

// ============== Knowledge API Extensions ==============

/**
 * Interface for external binding related operations
 */
export interface ExternalBindingApi {
  /** Registry for binding providers */
  readonly providers: BindingProviderRegistry

  /**
   * Search across all searchable providers or a specific one
   * @param keyword - Search keyword
   * @param provider - Optional provider name to limit search
   * @param type - Optional type filter
   * @returns Search results grouped by provider
   */
  search: (
    keyword: string,
    provider?: string,
    type?: string
  ) => Promise<Record<string, BindingSearchResult>>

  /**
   * List bindings for a knowledge base
   * @param kbId - Knowledge base ID
   * @param provider - Optional provider filter
   * @returns List of bindings
   */
  list: (kbId: number, provider?: string) => Promise<ExternalBinding[]>

  /**
   * Add a new binding
   * @param kbId - Knowledge base ID
   * @param data - Binding creation data
   * @returns Created binding
   */
  add: (kbId: number, data: ExternalBindingCreate) => Promise<ExternalBinding>

  /**
   * Remove a binding
   * @param kbId - Knowledge base ID
   * @param bindingId - Binding ID to remove
   */
  remove: (kbId: number, bindingId: number) => Promise<void>

  /**
   * Sync binding data from external system
   * @param kbId - Knowledge base ID
   * @param bindingId - Binding ID to sync
   */
  sync: (kbId: number, bindingId: number) => Promise<void>
}

/**
 * Global registry for binding providers
 * External packages can register their providers during app initialization
 */
export const bindingProviderRegistry = new BindingProviderRegistry()

/**
 * Global external binding API instance
 * External packages should set this during app initialization
 */
export let externalBindingApi: ExternalBindingApi | undefined

/**
 * Set the external binding API implementation
 * @param api - The API implementation
 */
export function setExternalBindingApi(api: ExternalBindingApi): void {
  externalBindingApi = api
}

/**
 * Check if external binding API is available
 * @returns True if binding API has been registered
 */
export function hasExternalBindingApi(): boolean {
  return externalBindingApi !== undefined
}

/**
 * Get the external binding API if available
 * @param throwIfMissing - Throw error if API not available
 * @returns The binding API or undefined
 * @throws Error if API is not available and throwIfMissing is true
 */
export function getExternalBindingApi(throwIfMissing = false): ExternalBindingApi | undefined {
  if (throwIfMissing && !externalBindingApi) {
    throw new Error(
      'External binding API is not available. Ensure the binding extension is registered.'
    )
  }
  return externalBindingApi
}

