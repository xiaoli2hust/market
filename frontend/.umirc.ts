import { defineConfig } from '@umijs/max';

export default defineConfig({
  title: '营销智能管理平台',
  npmClient: 'npm',
  hash: true,
  history: { type: 'browser' },
  antd: {
    configProvider: {
      theme: {
        token: {
          colorPrimary: '#C53A2C',
          colorInfo: '#C53A2C',
          colorBgLayout: '#F5EFE3',
          borderRadius: 2,
          fontFamily:
            '"Noto Sans SC", "PingFang SC", "Helvetica Neue", system-ui, -apple-system, sans-serif',
        },
        components: {
          Layout: {
            bodyBg: '#F5EFE3',
            headerBg: '#1A1714',
            siderBg: '#1A1714',
          },
          Menu: {
            darkItemBg: '#1A1714',
            darkSubMenuItemBg: '#1A1714',
            darkItemSelectedBg: '#C53A2C',
          },
        },
      },
    },
  },
  layout: false,
  request: {},
  initialState: {},
  model: {},
  access: {},
  mfsu: false,
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/user/login', component: './User/Login', layout: false },
    {
      path: '/',
      component: '@/layouts/EditorialLayout',
      routes: [
        { path: '/dashboard', component: './Dashboard', name: '日报看板' },
        { path: '/reports', component: './Reports', name: '报告中心' },
      ],
    },
  ],
  fastRefresh: true,
  esbuildMinifyIIFE: true,
  define: {
    'process.env.APP_NAME': '营销智能管理平台',
  },

});
