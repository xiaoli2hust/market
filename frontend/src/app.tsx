import type { RequestConfig } from '@umijs/max';
import { history } from '@umijs/max';
import { message, notification } from 'antd';
import { clearAuth, getCurrentUser, getToken } from '@/services/api';

/**
 * 初始全局状态：登录用户信息
 */
export async function getInitialState(): Promise<{
  currentUser?: ReturnType<typeof getCurrentUser>;
  token?: string | null;
}> {
  const token = getToken();
  // 清除无效的 dev token（让后端 JWT 生效）
  if (token && token.startsWith('dev.')) {
    clearAuth();
    return { currentUser: null, token: null };
  }
  return {
    currentUser: getCurrentUser(),
    token,
  };
}

/**
 * 路由守卫：未登录跳转登录页
 */
export function onRouteChange({ location }: { location: { pathname: string } }) {
  const token = getToken();
  if (!token && location.pathname !== '/user/login') {
    history.replace('/user/login');
  }
}

/**
 * 全局请求拦截 / 错误处理
 */
export const request: RequestConfig = {
  timeout: 15000,
  errorConfig: {
    errorThrower: (res: any) => {
      throw new Error(res?.message || 'Request error');
    },
    errorHandler: (error: any) => {
      const status = error?.response?.status;
      if (status === 401) {
        notification.warning({ message: '登录已失效，请重新登录' });
        clearAuth();
        history.replace('/user/login');
        return;
      }
      message.error(error?.message || '请求失败，请稍后重试');
    },
  },
  requestInterceptors: [
    (config: any) => {
      const token = getToken();
      if (token) {
        config.headers = { ...(config.headers || {}), Authorization: `Bearer ${token}` };
      }
      return config;
    },
  ],
};

// 注：使用自定义 EditorialLayout（见 src/layouts/EditorialLayout.tsx），
// .umirc.ts 中 layout: false 已禁用 ProLayout 内置布局。
