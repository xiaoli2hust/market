import React, { useState } from 'react';
import { Tabs, Tag } from 'antd';
import {
  CloudServerOutlined,
  RobotOutlined,
  SettingOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { WorkbenchPageHeader } from '@/components/workbench';
import CrawlerTab from './components/CrawlerTab';
import LLMTab from './components/LLMTab';
import UsersTab from './components/UsersTab';
import SettingsTab from './components/SettingsTab';
import './management.less';

const Management: React.FC = () => {
  const [tab, setTab] = useState(() => {
    if (typeof window === 'undefined') return 'crawler';
    return new URLSearchParams(window.location.search).get('tab') || 'crawler';
  });

  const handleTabChange = (key: string) => {
    setTab(key);
    if (typeof window !== 'undefined') {
      window.history.replaceState(null, '', `/management?tab=${key}`);
    }
  };

  return (
    <div className="mgmt">
      <WorkbenchPageHeader
        eyebrow="Command Center"
        title="管理"
        accent="中心"
        description="采集配置 · Agent 与模型 · 账号权限 · 外部集成 · 安全审计"
        extra={<Tag color="blue">所有关键操作均写入后端状态</Tag>}
      />

      <Tabs
        activeKey={tab}
        onChange={handleTabChange}
        className="mgmt-tabs edl-rise edl-rise-2"
        items={[
          { key: 'crawler', label: <span><CloudServerOutlined /> 采集配置</span>, children: <CrawlerTab /> },
          { key: 'llm', label: <span><RobotOutlined /> Agent 与模型</span>, children: <LLMTab /> },
          { key: 'users', label: <span><TeamOutlined /> 账号权限</span>, children: <UsersTab /> },
          { key: 'settings', label: <span><SettingOutlined /> 外部集成</span>, children: <SettingsTab /> },
        ]}
      />
    </div>
  );
};

export default Management;
