/**
 * NanoGridBot API Adapter
 *
 * This adapter maps HappyClaw frontend API calls to NanoGridBot backend responses.
 * It handles endpoint mapping and response transformation.
 */

import { api as originalApi, apiFetch } from './client';

// ============================================================================
// Type Definitions (matching HappyClaw frontend expectations)
// ============================================================================

export interface UserPublic {
  id: string;
  username: string;
  display_name: string;
  role: 'admin' | 'member';
  status: 'active' | 'disabled' | 'deleted';
  permissions: Permission[];
  must_change_password: boolean;
  disable_reason: string | null;
  notes: string | null;
  created_at: string;
  last_login_at: string | null;
  last_active_at: string | null;
  deleted_at: string | null;
  avatar_emoji: string | null;
  avatar_color: string | null;
  ai_name: string | null;
  ai_avatar_emoji: string | null;
  ai_avatar_color: string | null;
}

export type Permission =
  | 'manage_system_config'
  | 'manage_group_env'
  | 'manage_users'
  | 'manage_invites'
  | 'view_audit_log';

export interface SetupStatus {
  needsSetup: boolean;
  claudeConfigured: boolean;
  feishuConfigured: boolean;
}

export interface AppearanceConfig {
  appName: string;
  aiName: string;
  aiAvatarEmoji: string;
  aiAvatarColor: string;
}

export interface AuthLoginResponse {
  success: boolean;
  user: UserPublic;
  setupStatus?: SetupStatus;
  appearance?: AppearanceConfig;
}

export interface AuthStatusResponse {
  initialized: boolean;
}

// ============================================================================
// Group Types (matching backend GroupResponse)
// ============================================================================

interface BackendGroupResponse {
  jid: string;
  name: string;
  folder: string;
  active: boolean;
  trigger_pattern: string | null;
  requires_trigger: boolean;
}

/**
 * Frontend GroupInfo type (from ../types.ts)
 */
export interface FrontendGroupInfo {
  name: string;
  folder: string;
  added_at: string;
  kind?: 'home' | 'main' | 'feishu' | 'web';
  is_home?: boolean;
  is_my_home?: boolean;
  editable?: boolean;
  deletable?: boolean;
  lastMessage?: string;
  lastMessageTime?: string;
  execution_mode?: 'container' | 'host';
  custom_cwd?: string;
  created_by?: string;
  selected_skills?: string[] | null;
}

// ============================================================================
// Adapter Functions
// ============================================================================

/**
 * Check if system needs initial setup
 */
export async function checkAuthStatus(): Promise<AuthStatusResponse> {
  try {
    // Try the endpoint - if it doesn't exist, assume initialized
    return await apiFetch<AuthStatusResponse>('/api/auth/status', { method: 'GET' });
  } catch {
    // Backend doesn't have this endpoint - assume initialized
    return { initialized: true };
  }
}

/**
 * Setup initial admin user
 */
export async function setupAdmin(username: string, password: string): Promise<AuthLoginResponse> {
  // Map to register endpoint
  const response = await originalApi.post<{ token: string; user: any }>('/api/auth/register', {
    username,
    password,
  });

  return {
    success: true,
    user: mapUserResponse(response.user),
  };
}

/**
 * Change password
 */
export async function changePassword(_currentPassword: string, _newPassword: string): Promise<{ success: boolean; user: UserPublic }> {
  // TODO: Implement when backend supports this
  throw new Error('Not implemented: change password');
}

/**
 * Update profile
 */
export async function updateProfile(_payload: {
  username?: string;
  display_name?: string;
  avatar_emoji?: string | null;
  avatar_color?: string | null;
  ai_name?: string | null;
  ai_avatar_emoji?: string | null;
  ai_avatar_color?: string | null;
}): Promise<{ success: boolean; user: UserPublic }> {
  // TODO: Implement when backend supports this
  throw new Error('Not implemented: update profile');
}

/**
 * Fetch public appearance config
 */
export async function fetchAppearance(): Promise<AppearanceConfig> {
  try {
    return await apiFetch<AppearanceConfig>('/api/config/appearance/public', { method: 'GET' });
  } catch {
    // Return default appearance
    return {
      appName: 'NanoGridBot',
      aiName: 'NanoGridBot Assistant',
      aiAvatarEmoji: '🤖',
      aiAvatarColor: '#0d9488',
    };
  }
}

/**
 * Map backend group response to frontend GroupInfo format
 */
function mapBackendGroup(backendGroup: BackendGroupResponse): FrontendGroupInfo {
  // Determine group kind from folder name
  let kind: 'home' | 'main' | 'feishu' | 'web' = 'main';
  const folderLower = backendGroup.folder.toLowerCase();
  if (folderLower.includes('home') || folderLower === 'default') {
    kind = 'home';
  } else if (folderLower.includes('feishu') || folderLower.includes('lark')) {
    kind = 'feishu';
  } else if (folderLower.includes('web')) {
    kind = 'web';
  }

  return {
    name: backendGroup.name,
    folder: backendGroup.folder,
    added_at: new Date().toISOString(), // Backend doesn't provide this
    kind,
    is_home: kind === 'home',
    is_my_home: false,
    editable: true,
    deletable: true,
    execution_mode: 'container',
  };
}

/**
 * Fetch all groups from backend
 */
export async function fetchGroups(): Promise<{ groups: Record<string, FrontendGroupInfo> }> {
  const backendGroups = await apiFetch<BackendGroupResponse[]>('/api/groups', { method: 'GET' });

  const groups: Record<string, FrontendGroupInfo> = {};
  for (const group of backendGroups) {
    groups[group.folder] = mapBackendGroup(group);
  }

  return { groups };
}

/**
 * Fetch user's own groups
 */
export async function fetchUserGroups(): Promise<FrontendGroupInfo[]> {
  const backendGroups = await apiFetch<BackendGroupResponse[]>('/api/user/groups', { method: 'GET' });
  return backendGroups.map(mapBackendGroup);
}

// ============================================================================
// Helper Functions
// ============================================================================

function mapUserResponse(nanoUser: any): UserPublic {
  return {
    id: nanoUser.id?.toString() || '',
    username: nanoUser.username || '',
    display_name: nanoUser.display_name || nanoUser.username || '',
    role: nanoUser.role === 'owner' ? 'admin' : (nanoUser.role || 'member'),
    status: nanoUser.status || 'active',
    permissions: nanoUser.permissions || [],
    must_change_password: false,
    disable_reason: null,
    notes: null,
    created_at: nanoUser.created_at || new Date().toISOString(),
    last_login_at: null,
    last_active_at: null,
    deleted_at: null,
    avatar_emoji: null,
    avatar_color: null,
    ai_name: null,
    ai_avatar_emoji: null,
    ai_avatar_color: null,
  };
}

// ============================================================================
// Re-export original API with type overrides
// ============================================================================

export const api = {
  ...originalApi,

  // Auth endpoints with mapped responses
  login: async (username: string, password: string): Promise<AuthLoginResponse> => {
    const response = await originalApi.post<{ token: string; user: any }>('/api/auth/login', { username, password });
    return {
      success: true,
      user: mapUserResponse(response.user),
    };
  },

  register: async (payload: { username: string; password: string; display_name?: string; invite_code?: string }): Promise<AuthLoginResponse> => {
    const response = await originalApi.post<{ token: string; user: any }>('/api/auth/register', payload);
    return {
      success: true,
      user: mapUserResponse(response.user),
    };
  },

  // Groups endpoints with mapped responses
  getGroups: async (): Promise<{ groups: Record<string, FrontendGroupInfo> }> => {
    const backendGroups = await originalApi.get<BackendGroupResponse[]>('/api/groups');
    const groups: Record<string, FrontendGroupInfo> = {};
    for (const group of backendGroups) {
      groups[group.folder] = mapBackendGroup(group);
    }
    return { groups };
  },

  getUserGroups: async (): Promise<FrontendGroupInfo[]> => {
    const backendGroups = await originalApi.get<BackendGroupResponse[]>('/api/user/groups');
    return backendGroups.map(mapBackendGroup);
  },
};
