import { request } from '@@/exports';

/* ---------- 类型 ---------- */
export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResult {
  token?: string;
  user?: {
    id: number;
    name: string;
    role?: string;
    permissions?: string[];
    department?: string;
    security_warnings?: string[];
    must_change_password?: boolean;
  };
}

/* ---------- 鉴权 ---------- */
const SESSION_HINT_KEY = 'market_session_active';
const USER_KEY = 'market_user';

export function hasAuthSession(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(SESSION_HINT_KEY) === '1';
}

export function setAuth(user?: LoginResult['user']) {
  localStorage.setItem(SESSION_HINT_KEY, '1');
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(SESSION_HINT_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getCurrentUser(): LoginResult['user'] | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export async function fetchCurrentUser(): Promise<LoginResult['user'] | null> {
  try {
    const resp = await fetch('/api/auth/me', {
      method: 'GET',
      credentials: 'same-origin',
    });
    if (!resp.ok) {
      clearAuth();
      return null;
    }
    const data = await resp.json();
    const user = {
      id: data?.id || 0,
      name: data?.name || data?.username || '未命名用户',
      role: data?.role || 'viewer',
      permissions: data?.permissions || [],
      department: data?.department || '管理中心',
      security_warnings: data?.security_warnings || [],
      must_change_password: Boolean(data?.must_change_password),
    };
    setAuth(user);
    return user;
  } catch {
    clearAuth();
    return null;
  }
}

export async function logout() {
  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    });
  } finally {
    clearAuth();
  }
}

const ROLE_PERMISSIONS: Record<string, string[]> = {
  super_admin: ['*'],
  admin: [
    'dashboard:view',
    'dashboard:export',
    'reports:view',
    'reports:generate',
    'intelligence:view',
    'opportunities:view',
    'opportunities:manage',
    'bot:view',
    'bot:configure',
    'bot:knowledge',
    'bot:approve',
    'bot:evaluate',
    'bot:broadcast',
    'management:view',
    'management:crawler',
    'management:llm',
    'management:users',
    'management:settings',
    'management:express',
  ],
  viewer: ['dashboard:view', 'intelligence:view', 'opportunities:view'],
};

export const PERMISSION_LABELS: Record<string, string> = {
  'dashboard:view': '查看日报周报',
  'dashboard:export': '导出日报周报',
  'reports:view': '查看汇报材料',
  'reports:generate': '生成与推送汇报',
  'intelligence:view': '查看市场洞察',
  'opportunities:view': '查看商机中心',
  'opportunities:manage': '确认与流转线索',
  'bot:view': '查看机器人中心',
  'bot:configure': '配置机器人和 Skill',
  'bot:knowledge': '管理机器人知识空间',
  'bot:approve': '审批机器人外部动作',
  'bot:evaluate': '运行机器人评测',
  'bot:broadcast': '发送机器人群发消息',
  'management:view': '进入管理中心',
  'management:crawler': '管理采集任务',
  'management:llm': '管理模型与提示词',
  'management:users': '管理账号权限',
  'management:settings': '管理接口与密钥',
  'management:express': '生成标讯速递',
};

export function getPermissionLabel(permission: string): string {
  if (permission === '*') return '全部权限';
  return PERMISSION_LABELS[permission] || '未登记权限';
}

export function userHasPermission(user: LoginResult['user'] | null | undefined, permission: string): boolean {
  const permissions = user?.permissions?.length
    ? user.permissions
    : (ROLE_PERMISSIONS[user?.role || 'viewer'] || ROLE_PERMISSIONS.viewer);
  return permissions.includes('*') || permissions.includes(permission);
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (!error || typeof error !== 'object') return fallback;
  const e = error as Record<string, unknown>;
  const data = e.data as Record<string, unknown> | undefined;
  const response = e.response as Record<string, unknown> | undefined;
  const respData = response?.data as Record<string, unknown> | undefined;
  return (
    (data?.detail as string)
    || (data?.message as string)
    || (respData?.detail as string)
    || (respData?.message as string)
    || (e.message as string)
    || fallback
  );
}

/* ---------- 请求 ---------- */

/**
 * 登录。直接用 fetch 调用后端，避免 umi-request 的响应包装问题。
 */
export async function login(payload: LoginPayload): Promise<LoginResult> {
  if (!payload.username || !payload.password) {
    throw new Error('用户名或密码不能为空');
  }

  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody?.detail || `登录失败 (${resp.status})`);
    }

    const data = await resp.json();
    return {
      token: data?.token || data?.access_token,
      user: data?.user || { id: 0, name: payload.username, role: 'admin', department: '总部' },
    };
  } catch (err: any) {
    if (err?.message?.includes('Failed to fetch') || err?.message?.includes('NetworkError')) {
      throw new Error('无法连接到后端服务，请确认后端已启动');
    }
    throw err;
  }
}

export async function changeCurrentPassword(data: {
  current_password: string;
  new_password: string;
}) {
  return request('/api/auth/change-password', { method: 'POST', data });
}
