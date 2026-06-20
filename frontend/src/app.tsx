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
  return {
    currentUser: token ? getCurrentUser() : null,
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
    errorHandler: (error: any) => {
      const status = error?.response?.status || error?.status;
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
    (url: string, options: any) => {
      const token = getToken();
      if (token) {
        return {
          url,
          options: {
            ...options,
            headers: {
              ...(options?.headers || {}),
              Authorization: `Bearer ${token}`,
            },
          },
        };
      }
      return { url, options };
    },
  ],
};

// 注：使用自定义 EditorialLayout（见 src/layouts/EditorialLayout.tsx），
// .umirc.ts 中 layout: false 已禁用 ProLayout 内置布局。
