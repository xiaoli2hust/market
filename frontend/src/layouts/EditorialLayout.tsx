import React, { useEffect, useState } from 'react';
import { history, Outlet, useLocation } from '@@/exports';
import { Avatar, Button, Dropdown, Tag, Tooltip } from 'antd';
import {
  BarChartOutlined,
  ControlOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RadarChartOutlined,
  RiseOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { getCurrentUser, logout, userHasPermission } from '@/services/api';
import dayjs from 'dayjs';
import './editorial-layout.less';

/**
 * EditorialLayout
 * 编辑式数据驾驶舱布局：
 *  - 左侧"刊头"：刊名 / 期号 / 日期
 *  - 顶部黑色 menu bar（极细字号 + 字距）
 *  - 主内容采用纸张白盒，双栏式留白
 */
const EditorialLayout: React.FC = () => {
  const location = useLocation();
  const user = getCurrentUser();
  const can = (permission: string) => userHasPermission(user, permission);
  const today = dayjs().format('YYYY-MM-DD');
  const issue = `Vol. ${dayjs().format('YYYY')} / №${dayjs().format('YYYYMMDD')}`;
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem('market_sidebar_collapsed') === 'true';
  });

  useEffect(() => {
    if (!canAccessPath(location.pathname, can)) {
      history.replace('/dashboard');
    }
  }, [location.pathname, user?.role, user?.permissions]);

  const toggleCollapsed = () => {
    setCollapsed((value) => {
      const next = !value;
      if (typeof window !== 'undefined') {
        window.localStorage.setItem('market_sidebar_collapsed', String(next));
      }
      return next;
    });
  };

  const handleLogout = async () => {
    await logout();
    history.replace('/user/login');
  };

  return (
    <div className={`edl-shell ${collapsed ? 'is-sidebar-collapsed' : ''}`}>
      <aside className="edl-sidebar">
        <div className="edl-brand">
          <div className="edl-brand-mark">M</div>
          <div className="edl-brand-copy">
            <strong>Market</strong>
            <span>数据采集中心</span>
          </div>
          <Tooltip title={collapsed ? '展开导航' : '收起导航'} placement="right">
            <Button
              type="text"
              size="small"
              className="edl-collapse-btn"
              aria-label={collapsed ? '展开导航' : '收起导航'}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={toggleCollapsed}
            />
          </Tooltip>
        </div>
        <nav className="edl-subnav">
          {can('dashboard:view') && (
            <NavItem to="/dashboard" icon={<BarChartOutlined />} active={location.pathname.startsWith('/dashboard')}>
              日报周报
            </NavItem>
          )}
          {can('intelligence:view') && (
            <NavItem to="/intelligence" icon={<RadarChartOutlined />} active={location.pathname.startsWith('/intelligence')}>
              市场洞察
            </NavItem>
          )}
          {can('opportunities:view') && (
            <NavItem to="/opportunities" icon={<RiseOutlined />} active={location.pathname.startsWith('/opportunities')}>
              商机中心
            </NavItem>
          )}
          {can('management:view') && (
            <NavItem to="/management" icon={<ControlOutlined />} active={location.pathname.startsWith('/management')}>
              管理中心
            </NavItem>
          )}
        </nav>
        <div className="edl-sidebar-foot">
          <Tag icon={<DatabaseOutlined />} color="default"><span className="edl-sidebar-foot-label">内网优先</span></Tag>
          <span>{issue}</span>
        </div>
      </aside>

      <div className="edl-workspace">
        <header className="edl-topbar">
          <div>
            <div className="edl-topbar-title">{getCurrentPageTitle(location.pathname)}</div>
            <div className="edl-topbar-sub">Agent 采集 · 数据分析 · 管理复盘</div>
          </div>
          <div className="edl-topbar-right">
            <div className="edl-masthead-meta">
              <div className="edl-eyebrow">BUSINESS DAY</div>
              <div className="edl-masthead-date">{today}</div>
            </div>
            <Dropdown
              menu={{
                items: [
                  { key: 'logout', label: '退出登录', icon: <LogoutOutlined />, onClick: handleLogout },
                ],
              }}
              placement="bottomRight"
            >
              <div className="edl-user">
                <Avatar
                  size={30}
                  style={{ background: '#B42318', fontFamily: 'var(--display)' }}
                  icon={<UserOutlined />}
                >
                  {user?.name?.[0]}
                </Avatar>
                <span className="edl-user-name">{user?.name || '匿名'}</span>
              </div>
            </Dropdown>
          </div>
        </header>

        <main className="edl-main">
          <Outlet />
        </main>

        <footer className="edl-foot">
          <div className="edl-foot-inner">
            <span>© {dayjs().format('YYYY')} Market 数据采集中心</span>
            <span>内部数据 · 授权访问</span>
          </div>
        </footer>
      </div>
    </div>
  );
};

function canAccessPath(pathname: string, can: (permission: string) => boolean): boolean {
  if (pathname.startsWith('/management')) return can('management:view');
  if (pathname.startsWith('/intelligence')) return can('intelligence:view');
  if (pathname.startsWith('/opportunities')) return can('opportunities:view');
  if (pathname.startsWith('/dashboard')) return can('dashboard:view');
  return true;
}

const NavItem: React.FC<{
  to: string;
  active?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}> = ({ to, active, disabled, icon, children }) => (
  <a
    className={`edl-nav-item ${active ? 'is-active' : ''} ${disabled ? 'is-disabled' : ''}`}
    onClick={(e) => {
      e.preventDefault();
      if (!disabled) history.push(to);
    }}
  >
    {icon && <span className="edl-nav-icon">{icon}</span>}
    <span className="edl-nav-label">{children}</span>
  </a>
);

function getCurrentPageTitle(pathname: string): string {
  if (pathname.startsWith('/management')) return '管理中心';
  if (pathname.startsWith('/intelligence/opportunities')) return '标讯线索确认';
  if (pathname.startsWith('/intelligence')) return '市场洞察';
  if (pathname.startsWith('/opportunities')) return '商机中心';
  return '日报周报';
}

export default EditorialLayout;
