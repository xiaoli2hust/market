import '@umijs/max/typings';

declare module '*.less';
declare module '*.css';
declare module '*.svg' {
  const url: string;
  export default url;
}

declare global {
  interface Window {
    __MARKET_TOKEN__?: string;
  }
}
