import { defineConfig } from '@umijs/max';

export default defineConfig({
  title: '营销数据驾驶舱',
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
      target: 'http://127.0.0.1:8001',
      changeOrigin: true,
    },
    '/r': {
      target: 'http://127.0.0.1:8001',
      changeOrigin: true,
    },
    '/re': {
      target: 'http://127.0.0.1:8001',
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
        { path: '/dashboard', component: './Dashboard', name: '日报周报' },
        { path: '/intelligence', component: './Intelligence', name: '资讯中心' },
        { path: '/opportunities', component: './Opportunities', name: '商机数据' },
        { path: '/management', component: './Management', name: '管理中心' },
      ],
    },
  ],
  fastRefresh: true,
  esbuildMinifyIIFE: true,
  define: {
    'process.env.APP_NAME': '营销数据驾驶舱',
  },

});
