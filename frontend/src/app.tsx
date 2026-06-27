import type { RequestConfig } from '@@/exports';
import { history } from '@@/exports';
import { App as AntdApp, ConfigProvider, message, notification } from 'antd';
import {
  clearAuth,
  fetchCurrentUser,
  getApiErrorMessage,
  getCurrentUser,
  hasAuthSession,
  logout,
} from '@/services/api';

ConfigProvider.config({
  holderRender: (children) => <AntdApp>{children}</AntdApp>,
});

/**
 * 初始全局状态：登录用户信息
 */
export async function getInitialState(): Promise<{
  currentUser?: ReturnType<typeof getCurrentUser>;
}> {
  if (typeof window !== 'undefined' && window.location.pathname === '/user/login') {
    return { currentUser: null };
  }
  const currentUser = await fetchCurrentUser();
  return {
    currentUser,
  };
}

/**
 * 路由守卫：未登录跳转登录页
 */
export function onRouteChange({ location }: { location: { pathname: string } }) {
  if (!hasAuthSession() && !getCurrentUser() && location.pathname !== '/user/login') {
    history.replace('/user/login');
  }
}

/**
 * 全局请求拦截 / 错误处理
 */
export const request: RequestConfig = {
  timeout: 15000,
  errorConfig: {
    errorHandler: (error: unknown) => {
      const e = error as Record<string, unknown>;
      const response = e?.response as Record<string, unknown> | undefined;
      const status = (response?.status as number) || (e?.status as number);
      if (status === 401) {
        notification.warning({ message: '登录已失效，请重新登录' });
        clearAuth();
        void logout();
        history.replace('/user/login');
        return;
      }
      message.error(getApiErrorMessage(error, '请求失败，请稍后重试'));
    },
  },
  requestInterceptors: [
    (url: string, options: Record<string, unknown>) => {
      // 添加 CSRF 防护头部 + 凭证
      const headers = (options.headers as Record<string, string>) || {};
      return {
        url,
        options: {
          ...options,
          credentials: 'same-origin',
          headers: {
            ...headers,
            'X-Requested-With': 'XMLHttpRequest',
          },
        },
      };
    },
  ],
};

// 注：使用自定义 EditorialLayout（见 src/layouts/EditorialLayout.tsx），
// .umirc.ts 中 layout: false 已禁用 ProLayout 内置布局。
