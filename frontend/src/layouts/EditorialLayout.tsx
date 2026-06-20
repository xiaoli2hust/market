import React from 'react';
import { history, Outlet, useLocation } from '@umijs/max';
import { Avatar, Dropdown } from 'antd';
import { LogoutOutlined, UserOutlined } from '@ant-design/icons';
import { clearAuth, getCurrentUser } from '@/services/api';
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
  const today = dayjs().format('YYYY · MM · DD');
  const issue = `Vol. ${dayjs().format('YYYY')} / №${dayjs().format('DDD')}`;

  const handleLogout = () => {
    clearAuth();
    history.replace('/user/login');
  };

  return (
    <div className="edl-shell">
      {/* 顶部刊头 */}
      <header className="edl-masthead">
        <div className="edl-masthead-inner">
          <div className="edl-masthead-left">
            <div className="edl-eyebrow">采集 · 洞察 · 驱动</div>
            <h1 className="edl-masthead-title">
              <span className="edl-masthead-zh">营销数据驾驶舱</span>
              <span className="edl-masthead-en">Marketing Data Cockpit</span>
            </h1>
          </div>
          <div className="edl-masthead-right">
            <div className="edl-masthead-meta">
              <div className="edl-eyebrow">{issue}</div>
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
                  size={32}
                  style={{ background: '#C53A2C', fontFamily: 'var(--display)' }}
                  icon={<UserOutlined />}
                >
                  {user?.name?.[0]}
                </Avatar>
                <span className="edl-user-name">{user?.name || '匿名'}</span>
              </div>
            </Dropdown>
          </div>
        </div>
        <hr className="edl-rule-strong" />
        <div className="edl-subnav">
          <NavItem to="/dashboard" active={location.pathname.startsWith('/dashboard')}>
            01 · 日报周报
          </NavItem>
          <NavItem to="/intelligence" active={location.pathname.startsWith('/intelligence')}>
            02 · 资讯中心
          </NavItem>
          <NavItem to="/opportunities" active={location.pathname.startsWith('/opportunities')}>
            03 · 商机数据
          </NavItem>
          <NavItem to="/management" active={location.pathname.startsWith('/management')}>
            04 · 管理中心
          </NavItem>
        </div>
        <hr className="edl-rule" />
      </header>

      <main className="edl-main">
        <Outlet />
      </main>

      <footer className="edl-foot">
        <hr className="edl-rule" />
        <div className="edl-foot-inner">
          <span className="edl-eyebrow">© {dayjs().format('YYYY')} Marketing Data Cockpit</span>
          <span className="edl-eyebrow">编辑部 · 内部限阅</span>
        </div>
      </footer>
    </div>
  );
};

const NavItem: React.FC<{
  to: string;
  active?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}> = ({ to, active, disabled, children }) => (
  <a
    className={`edl-nav-item ${active ? 'is-active' : ''} ${disabled ? 'is-disabled' : ''}`}
    onClick={(e) => {
      e.preventDefault();
      if (!disabled) history.push(to);
    }}
  >
    {children}
  </a>
);

export default EditorialLayout;
