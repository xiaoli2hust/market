import { defineConfig } from '@umijs/max';

const apiProxyTarget = process.env.API_PROXY_TARGET || 'http://127.0.0.1:8001';

export default defineConfig({
  title: 'Market 数据采集中心',
  npmClient: 'npm',
  hash: true,
  history: { type: 'browser' },
  antd: {
    configProvider: {
      theme: {
        token: {
          colorPrimary: '#C53A2C',
          colorInfo: '#C53A2C',
          colorBgLayout: '#F6F7F9',
          borderRadius: 6,
          fontFamily:
            '"Noto Sans SC", "PingFang SC", "Helvetica Neue", system-ui, -apple-system, sans-serif',
        },
        components: {
          Layout: {
            bodyBg: '#F6F7F9',
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
      target: apiProxyTarget,
      changeOrigin: true,
    },
    '/r': {
      target: apiProxyTarget,
      changeOrigin: true,
    },
    '/re': {
      target: apiProxyTarget,
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
        { path: '/intelligence/opportunities', component: './OpportunityRadar', name: '标讯线索确认' },
        { path: '/intelligence', component: './Intelligence', name: '市场洞察' },
        { path: '/opportunities', component: './Opportunities', name: '商机中心' },
        { path: '/management', component: './Management', name: '管理中心' },
      ],
    },
  ],
  fastRefresh: true,
  esbuildMinifyIIFE: true,
  define: {
    'process.env.APP_NAME': 'Market 数据采集中心',
  },

});
