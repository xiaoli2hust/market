import React from 'react';
import { history } from '@@/exports';
import { Tabs } from 'antd';
import {
  ApiOutlined,
  AuditOutlined,
  ClockCircleOutlined,
  RobotOutlined,
  SettingOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import {
  WorkbenchMetricGrid,
  WorkbenchPageHeader,
  WorkbenchStatusRail,
} from '@/components/workbench';
import { formatTime } from './botCenterShared';
import { useBotCenterController } from './useBotCenterController';
import {
  renderBroadcastTab,
  renderChannelsTab,
  renderChatTab,
  renderCollaborationTab,
  renderComplianceTab,
  renderEvaluationTab,
  renderKnowledgeTab,
  renderLogsTab,
  renderReleaseTab,
  renderSkillsTab,
  renderTasksTab,
} from './botCenterViews';
import './bot-center.less';

const BotCenter: React.FC = () => {
  const controller = useBotCenterController();
  const {
    activeTab,
    adapters,
    boundSkills,
    botCenterViewContext,
    handleNewConversation,
    inboxTotal,
    knowledgeTotal,
    overview,
    profiles,
    qualitySummary,
    selectedProfileData,
    setActiveTab,
    skills,
    taskTotal,
  } = controller;

  return (
    <div className="bot-center">
      <WorkbenchPageHeader
        eyebrow="AGENT OPERATIONS"
        title="机器人中心"
        accent="Agent"
        description="机器人接入、Skill 编排、知识检索、对话测试、群发通知和运行审计的统一工作台。"
        actions={[
          { label: '管理配置', icon: <SettingOutlined />, onClick: () => history.push('/management') },
          { label: '新建测试', icon: <RobotOutlined />, onClick: handleNewConversation },
        ]}
      />

      <WorkbenchStatusRail
        items={[
          { label: '机器人 Profile', value: `${overview?.profiles ?? profiles.length} 个`, status: 'good', meta: '身份、边界和 Skill 绑定' },
          { label: '已启用 Skill', value: `${overview?.enabled_skills ?? skills.filter((item) => item.enabled).length} 个`, status: 'good', meta: '受控能力包，不靠 Prompt 硬猜' },
          { label: '知识文件', value: `${overview?.knowledge_files ?? knowledgeTotal} 份`, status: knowledgeTotal ? 'good' : 'warn', meta: '可追溯检索来源' },
          { label: '待审批动作', value: `${overview?.pending_approvals ?? qualitySummary?.pending_actions ?? 0} 个`, status: (overview?.pending_approvals ?? 0) ? 'warn' : 'good', meta: '外部动作先审批再执行' },
          { label: '生产收件箱', value: `${overview?.open_inbox ?? inboxTotal} 个`, status: (overview?.open_inbox ?? inboxTotal) ? 'warn' : 'good', meta: '入站消息、接管和处理闭环' },
          { label: '最近运行', value: overview?.latest_run_at ? formatTime(overview.latest_run_at) : '暂无', status: overview?.latest_run_at ? 'muted' : 'warn', meta: '每次调用都有日志' },
        ]}
      />

      <WorkbenchMetricGrid
        metrics={[
          { label: '当前机器人', value: selectedProfileData?.name || '未选择', icon: <RobotOutlined />, tone: 'blue', hint: selectedProfileData?.description || '选择一个机器人开始测试' },
          { label: '绑定 Skill', value: boundSkills.length, icon: <ToolOutlined />, tone: 'purple', hint: '只调用已绑定且已启用的 Skill' },
          { label: '自动任务', value: overview?.active_tasks ?? taskTotal, icon: <ClockCircleOutlined />, tone: 'green', hint: '按计划或人工触发运行' },
          { label: '评测风险', value: qualitySummary?.failed_evaluation_runs ?? overview?.failed_evaluations ?? 0, icon: <AuditOutlined />, tone: 'gold', hint: '失败用例进入纠错闭环' },
          { label: '渠道适配器', value: overview?.enabled_adapters ?? adapters.filter((item) => item.status === 'enabled').length, icon: <ApiOutlined />, tone: 'blue', hint: '签名、限流、重试和能力声明' },
        ]}
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'chat', label: '对话测试台', forceRender: true, children: renderChatTab(botCenterViewContext) },
          { key: 'skills', label: '配置运营', forceRender: true, children: renderSkillsTab(botCenterViewContext) },
          { key: 'knowledge', label: '知识空间', forceRender: true, children: renderKnowledgeTab(botCenterViewContext) },
          { key: 'channels', label: '生产运营', forceRender: true, children: renderChannelsTab(botCenterViewContext) },
          { key: 'tasks', label: '任务审批', forceRender: true, children: renderTasksTab(botCenterViewContext) },
          { key: 'release', label: '发布观测', forceRender: true, children: renderReleaseTab(botCenterViewContext) },
          { key: 'evaluation', label: '评测纠错', forceRender: true, children: renderEvaluationTab(botCenterViewContext) },
          { key: 'collaboration', label: '协作治理', forceRender: true, children: renderCollaborationTab(botCenterViewContext) },
          { key: 'compliance', label: '合规环境', forceRender: true, children: renderComplianceTab(botCenterViewContext) },
          { key: 'broadcast', label: '消息群发', forceRender: true, children: renderBroadcastTab(botCenterViewContext) },
          { key: 'logs', label: '运行日志', forceRender: true, children: renderLogsTab(botCenterViewContext) },
        ]}
      />
    </div>
  );
};

export default BotCenter;
