import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { history } from '@@/exports';
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Upload,
  message,
} from 'antd';
import {
  ApiOutlined,
  AuditOutlined,
  BellOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloudUploadOutlined,
  DatabaseOutlined,
  ExclamationCircleOutlined,
  FieldTimeOutlined,
  FileSearchOutlined,
  RobotOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
  TeamOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  BotAuditLog,
  BotBroadcastItem,
  BotBroadcastPayload,
  BotBroadcastStatus,
  BotChannelBinding,
  BotChatTestResult,
  BotEvidenceRecord,
  BotKnowledgeFile,
  BotMessage,
  BotMessageType,
  BotOverview,
  BotProfile,
  BotSkill,
  BotSkillRun,
  createBotBroadcast,
  createBotKnowledgeText,
  fetchBotAuditLogs,
  fetchBotBroadcasts,
  fetchBotChannelBindings,
  fetchBotConversations,
  fetchBotKnowledgeFiles,
  fetchBotOverview,
  fetchBotProfiles,
  fetchBotSkillRuns,
  fetchBotSkills,
  getApiErrorMessage,
  getCurrentUser,
  runBotChatTest,
  searchBotKnowledge,
  sendBotBroadcast,
  sendExistingBotBroadcast,
  updateBotSkill,
  uploadBotKnowledgeFile,
  userHasPermission,
} from '@/services/api';
import {
  WorkbenchMetricGrid,
  WorkbenchPageHeader,
  WorkbenchSection,
  WorkbenchStatusRail,
} from '@/components/workbench';
import './bot-center.less';

const PAGE_SIZE = 10;

const STATUS_META: Record<BotBroadcastStatus, { label: string; color: string; icon: React.ReactNode }> = {
  draft: { label: '草稿', color: 'default', icon: <ClockCircleOutlined /> },
  sending: { label: '发送中', color: 'processing', icon: <FieldTimeOutlined /> },
  sent: { label: '已发送', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '发送失败', color: 'error', icon: <ExclamationCircleOutlined /> },
};

const NOTICE_TYPE_OPTIONS = [
  { value: 'general', label: '普通通知' },
  { value: 'daily_report', label: '日报周报' },
  { value: 'market_digest', label: '市场速递' },
  { value: 'bidding_alert', label: '标讯提醒' },
  { value: 'task_followup', label: '任务提醒' },
];

const MESSAGE_TYPE_OPTIONS: Array<{ value: BotMessageType; label: string }> = [
  { value: 'markdown', label: '图文排版' },
  { value: 'text', label: '纯文本' },
];

const DEFAULT_BROADCAST_FORM: Partial<BroadcastFormValues> = {
  message_type: 'markdown',
  notice_type: 'general',
  target_type: 'configured_group',
  at_all: false,
};

const DEFAULT_KNOWLEDGE_FORM: Partial<KnowledgeFormValues> = {
  category: 'general',
};

const KNOWLEDGE_CATEGORIES = [
  { value: 'general', label: '通用资料' },
  { value: 'product', label: '产品方案' },
  { value: 'spatial_data', label: '空间数据' },
  { value: 'policy', label: '政策制度' },
  { value: 'weekly_report', label: '周报材料' },
  { value: 'customer', label: '客户资料' },
];

type BroadcastFormValues = BotBroadcastPayload & { notice_type?: string };
type KnowledgeFormValues = { title: string; category: string; text_content: string };

const BotCenter: React.FC = () => {
  const currentUser = getCurrentUser();
  const canBroadcast = userHasPermission(currentUser, 'bot:broadcast');
  const [activeTab, setActiveTab] = useState('chat');
  const [loading, setLoading] = useState(false);
  const [overview, setOverview] = useState<BotOverview | null>(null);
  const [profiles, setProfiles] = useState<BotProfile[]>([]);
  const [skills, setSkills] = useState<BotSkill[]>([]);
  const [selectedProfile, setSelectedProfile] = useState('management_assistant_agent');

  const [chatInput, setChatInput] = useState('');
  const [simulatedRole, setSimulatedRole] = useState('经营管理者');
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [chatMessages, setChatMessages] = useState<BotMessage[]>([]);
  const [chatResult, setChatResult] = useState<BotChatTestResult | null>(null);
  const [chatSending, setChatSending] = useState(false);

  const [broadcastForm] = Form.useForm<BroadcastFormValues>();
  const [broadcasts, setBroadcasts] = useState<BotBroadcastItem[]>([]);
  const [broadcastTotal, setBroadcastTotal] = useState(0);
  const [broadcastStatusFilter, setBroadcastStatusFilter] = useState<BotBroadcastStatus | 'all'>('all');
  const [broadcastSaving, setBroadcastSaving] = useState(false);
  const [broadcastSending, setBroadcastSending] = useState(false);
  const [resendingId, setResendingId] = useState<number | null>(null);

  const [knowledgeForm] = Form.useForm<KnowledgeFormValues>();
  const [knowledgeFiles, setKnowledgeFiles] = useState<BotKnowledgeFile[]>([]);
  const [knowledgeTotal, setKnowledgeTotal] = useState(0);
  const [knowledgeFile, setKnowledgeFile] = useState<File | null>(null);
  const [knowledgeUploading, setKnowledgeUploading] = useState(false);
  const [knowledgeQuery, setKnowledgeQuery] = useState('');
  const [knowledgeSearchResult, setKnowledgeSearchResult] = useState<BotEvidenceRecord[]>([]);

  const [bindings, setBindings] = useState<BotChannelBinding[]>([]);
  const [skillRuns, setSkillRuns] = useState<BotSkillRun[]>([]);
  const [auditLogs, setAuditLogs] = useState<BotAuditLog[]>([]);

  const loadCore = useCallback(async () => {
    setLoading(true);
    try {
      const [overviewResp, profileResp, skillResp] = await Promise.all([
        fetchBotOverview(),
        fetchBotProfiles(),
        fetchBotSkills(),
      ]);
      setOverview(overviewResp);
      setProfiles(profileResp || []);
      setSkills(skillResp || []);
      if (!selectedProfile && profileResp?.[0]?.profile_key) {
        setSelectedProfile(profileResp[0].profile_key);
      }
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载机器人配置失败'));
    } finally {
      setLoading(false);
    }
  }, [selectedProfile]);

  const loadBroadcasts = useCallback(async () => {
    try {
      const resp = await fetchBotBroadcasts({
        page: 1,
        page_size: PAGE_SIZE,
        status: broadcastStatusFilter === 'all' ? undefined : broadcastStatusFilter,
      });
      setBroadcasts(resp?.items || []);
      setBroadcastTotal(resp?.total || 0);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载群发记录失败'));
    }
  }, [broadcastStatusFilter]);

  const loadKnowledge = useCallback(async () => {
    try {
      const resp = await fetchBotKnowledgeFiles({ page: 1, page_size: PAGE_SIZE });
      setKnowledgeFiles(resp?.items || []);
      setKnowledgeTotal(resp?.total || 0);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载知识空间失败'));
    }
  }, []);

  const loadOps = useCallback(async () => {
    try {
      const [bindingResp, runResp, auditResp] = await Promise.all([
        fetchBotChannelBindings(),
        fetchBotSkillRuns({ page: 1, page_size: PAGE_SIZE }),
        fetchBotAuditLogs({ page: 1, page_size: PAGE_SIZE }),
      ]);
      setBindings(bindingResp || []);
      setSkillRuns(runResp?.items || []);
      setAuditLogs(auditResp?.items || []);
    } catch {
      // 局部日志加载失败不影响对话台。
    }
  }, []);

  useEffect(() => {
    loadCore();
    loadBroadcasts();
    loadKnowledge();
    loadOps();
  }, [loadBroadcasts, loadCore, loadKnowledge, loadOps]);

  const selectedProfileData = useMemo(
    () => profiles.find((item) => item.profile_key === selectedProfile),
    [profiles, selectedProfile],
  );

  const boundSkills = useMemo(() => {
    const allowed = new Set(selectedProfileData?.allowed_skills || []);
    return skills.filter((skill) => allowed.has(skill.skill_key));
  }, [selectedProfileData, skills]);

  const handleChatSend = async () => {
    const text = chatInput.trim();
    if (!text) {
      message.warning('请输入测试问题');
      return;
    }
    setChatSending(true);
    try {
      const result = await runBotChatTest({
        profile_key: selectedProfile,
        message: text,
        conversation_id: conversationId,
        simulated_user_role: simulatedRole,
      });
      setConversationId(result.conversation.conversation_id);
      setChatResult(result);
      setChatMessages((prev) => [...prev, result.user_message, result.assistant_message]);
      setChatInput('');
      await Promise.all([loadCore(), loadOps()]);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '对话测试失败'));
    } finally {
      setChatSending(false);
    }
  };

  const handleNewConversation = () => {
    setConversationId(undefined);
    setChatMessages([]);
    setChatResult(null);
  };

  const handleToggleSkill = async (skill: BotSkill, enabled: boolean) => {
    try {
      const updated = await updateBotSkill(skill.skill_key, { enabled });
      setSkills((prev) => prev.map((item) => item.skill_key === updated.skill_key ? updated : item));
      message.success(enabled ? 'Skill 已启用' : 'Skill 已停用');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '更新 Skill 失败'));
    }
  };

  const buildBroadcastPayload = async (): Promise<BotBroadcastPayload> => {
    const values = await broadcastForm.validateFields();
    return {
      title: values.title.trim(),
      content: values.content.trim(),
      message_type: values.message_type || 'markdown',
      target_type: 'configured_group',
      at_all: Boolean(values.at_all),
      target_payload: {
        notice_type: values.notice_type || 'general',
        requested_by: currentUser?.name || currentUser?.role || '系统用户',
      },
    };
  };

  const resetBroadcastForm = () => {
    broadcastForm.resetFields();
    broadcastForm.setFieldsValue(DEFAULT_BROADCAST_FORM);
  };

  const handleSaveDraft = async () => {
    if (!canBroadcast) return;
    setBroadcastSaving(true);
    try {
      await createBotBroadcast(await buildBroadcastPayload());
      resetBroadcastForm();
      setBroadcastStatusFilter('all');
      await loadBroadcasts();
      message.success('群发草稿已保存');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '保存草稿失败'));
    } finally {
      setBroadcastSaving(false);
    }
  };

  const handleSendNow = async () => {
    if (!canBroadcast) return;
    setBroadcastSending(true);
    try {
      const result = await sendBotBroadcast(await buildBroadcastPayload());
      resetBroadcastForm();
      setBroadcastStatusFilter('all');
      await loadBroadcasts();
      if (result.status === 'sent') message.success('消息已发送到钉钉群');
      else message.error(result.error_message || result.result_message || '消息发送失败');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '发送失败'));
    } finally {
      setBroadcastSending(false);
    }
  };

  const handleResend = async (record: BotBroadcastItem) => {
    if (!canBroadcast) return;
    setResendingId(record.id);
    try {
      const result = await sendExistingBotBroadcast(record.id);
      await loadBroadcasts();
      if (result.status === 'sent') message.success('消息已重新发送');
      else message.error(result.error_message || result.result_message || '重新发送失败');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '重新发送失败'));
    } finally {
      setResendingId(null);
    }
  };

  const handleCreateKnowledge = async () => {
    if (!canBroadcast) return;
    setKnowledgeUploading(true);
    try {
      const values = await knowledgeForm.validateFields();
      await createBotKnowledgeText(values);
      knowledgeForm.resetFields();
      knowledgeForm.setFieldsValue(DEFAULT_KNOWLEDGE_FORM);
      await loadKnowledge();
      message.success('知识文本已入库并切片');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '知识入库失败'));
    } finally {
      setKnowledgeUploading(false);
    }
  };

  const handleUploadKnowledge = async () => {
    if (!canBroadcast || !knowledgeFile) {
      message.warning('请选择要上传的知识文件');
      return;
    }
    setKnowledgeUploading(true);
    try {
      const title = knowledgeForm.getFieldValue('title') || knowledgeFile.name;
      const category = knowledgeForm.getFieldValue('category') || 'general';
      await uploadBotKnowledgeFile({ title, category, file: knowledgeFile });
      setKnowledgeFile(null);
      await loadKnowledge();
      message.success('知识文件已上传并建立索引');
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '知识文件上传失败'));
    } finally {
      setKnowledgeUploading(false);
    }
  };

  const handleSearchKnowledge = async () => {
    if (!knowledgeQuery.trim()) {
      message.warning('请输入检索问题');
      return;
    }
    try {
      const resp = await searchBotKnowledge(knowledgeQuery.trim());
      setKnowledgeSearchResult(resp.evidence_records || []);
      message.success(`命中 ${resp.evidence_records?.length || 0} 条证据`);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '知识检索失败'));
    }
  };

  const profileOptions = profiles.map((item) => ({ value: item.profile_key, label: item.name }));

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
          { label: '最近运行', value: overview?.latest_run_at ? formatTime(overview.latest_run_at) : '暂无', status: overview?.latest_run_at ? 'muted' : 'warn', meta: '每次调用都有日志' },
        ]}
      />

      <WorkbenchMetricGrid
        metrics={[
          { label: '当前机器人', value: selectedProfileData?.name || '未选择', icon: <RobotOutlined />, tone: 'blue', hint: selectedProfileData?.description || '选择一个机器人开始测试' },
          { label: '绑定 Skill', value: boundSkills.length, icon: <ToolOutlined />, tone: 'purple', hint: '只调用已绑定且已启用的 Skill' },
          { label: '群聊绑定', value: bindings.length, icon: <TeamOutlined />, tone: 'green', hint: '钉钉群与机器人 Profile 的关系' },
          { label: '群发记录', value: broadcastTotal, icon: <BellOutlined />, tone: 'gold', hint: '消息群发仍是受控动作' },
        ]}
      />

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'chat', label: '对话测试台', children: renderChatTab() },
          { key: 'skills', label: 'Skill 管理', children: renderSkillsTab() },
          { key: 'knowledge', label: '知识空间', children: renderKnowledgeTab() },
          { key: 'channels', label: '群聊接入', children: renderChannelsTab() },
          { key: 'broadcast', label: '消息群发', children: renderBroadcastTab() },
          { key: 'logs', label: '运行日志', children: renderLogsTab() },
        ]}
      />
    </div>
  );

  function renderChatTab() {
    return (
      <div className="bot-chat-grid">
        <WorkbenchSection title="对话测试台" description="像真实用户一样提问，右侧展示本轮调用了哪些 Skill、命中了哪些证据。">
          <Spin spinning={loading || chatSending}>
            <div className="bot-chat-toolbar">
              <Select
                value={selectedProfile}
                options={profileOptions}
                onChange={(value) => {
                  setSelectedProfile(value);
                  const profile = profiles.find((item) => item.profile_key === value);
                  setSimulatedRole(profile?.default_role || '经营管理者');
                  handleNewConversation();
                }}
              />
              <Input
                value={simulatedRole}
                onChange={(event) => setSimulatedRole(event.target.value)}
                placeholder="模拟用户身份"
              />
              <Button onClick={handleNewConversation}>清空会话</Button>
            </div>
            <div className="bot-chat-window">
              {chatMessages.length ? chatMessages.map((item) => (
                <div className={`bot-chat-message role-${item.role}`} key={`${item.role}-${item.id}-${item.created_at}`}>
                  <span>{item.role === 'user' ? simulatedRole || '用户' : selectedProfileData?.name || '机器人'}</span>
                  <p>{item.content}</p>
                </div>
              )) : <Empty description="输入问题后开始测试机器人能力" />}
            </div>
            <div className="bot-chat-input">
              <Input.TextArea
                data-testid="bot-chat-input"
                rows={4}
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                placeholder="例如：分析一下今年公安、政数、空间数据相关标讯和政策机会"
              />
              <Button data-testid="bot-chat-send" type="primary" icon={<SendOutlined />} loading={chatSending} onClick={handleChatSend}>
                发送测试
              </Button>
            </div>
          </Spin>
        </WorkbenchSection>

        <div className="bot-agent-side">
          <WorkbenchSection title="本轮调用链" description="每次回答都必须能追踪 Skill 和证据。">
            {chatResult?.selected_skills?.length ? (
              <div className="bot-skill-trace">
                {chatResult.selected_skills.map((run) => (
                  <div className="bot-trace-item" key={run.run_id}>
                    <div>
                      <strong>{run.skill_name || run.skill_key}</strong>
                      <Tag color={run.status === 'success' ? 'success' : 'error'}>{run.status}</Tag>
                    </div>
                    <span>{run.duration_ms ?? 0} ms · {run.evidence_records?.length || 0} 条证据</span>
                  </div>
                ))}
              </div>
            ) : <Empty description="暂无调用链" />}
          </WorkbenchSection>

          <WorkbenchSection title="证据命中" description="关键结论必须来自这些证据。">
            <EvidenceList evidence={chatResult?.evidence_records || []} />
          </WorkbenchSection>
        </div>
      </div>
    );
  }

  function renderSkillsTab() {
    return (
      <WorkbenchSection title="Skill 管理" description="Skill 是机器人能力包；这里管理启停、契约、证据要求和最近运行。">
        <Table
          className="edl-table"
          rowKey="skill_key"
          dataSource={skills}
          pagination={false}
          scroll={{ x: 980 }}
          columns={[
            {
              title: 'Skill',
              width: 260,
              render: (_: unknown, record: BotSkill) => (
                <div className="bot-table-title">
                  <strong>{record.name}</strong>
                  <span>{record.skill_key}</span>
                </div>
              ),
            },
            { title: '分类', dataIndex: 'category', width: 110, render: (value: string) => <Tag>{value}</Tag> },
            { title: '触发场景', dataIndex: 'trigger_scenarios', render: (value: string[]) => <span>{(value || []).join('；')}</span> },
            { title: '权限', dataIndex: 'required_permission', width: 150, render: (value: string) => value ? <Tag color="blue">{value}</Tag> : <Tag>无</Tag> },
            {
              title: '状态',
              width: 120,
              render: (_: unknown, record: BotSkill) => (
                <Switch
                  data-testid={`bot-skill-switch-${record.skill_key}`}
                  checked={record.enabled}
                  onChange={(checked) => handleToggleSkill(record, checked)}
                  disabled={!canBroadcast}
                />
              ),
            },
          ]}
        />
      </WorkbenchSection>
    );
  }

  function renderKnowledgeTab() {
    return (
      <div className="bot-knowledge-grid">
        <WorkbenchSection title="知识入库" description="支持文本、HTML、Markdown、TXT；入库后会切片并用于测试台检索。">
          {!canBroadcast && <Alert type="warning" showIcon message="当前账号只能查看知识，不能新增知识。" />}
          <Form<KnowledgeFormValues>
            form={knowledgeForm}
            layout="vertical"
            disabled={!canBroadcast}
            initialValues={DEFAULT_KNOWLEDGE_FORM}
          >
            <div className="bot-form-row">
              <Form.Item label="标题" name="title" rules={[{ required: true, message: '请输入知识标题' }]}>
                <Input data-testid="bot-knowledge-title" placeholder="例如：空间数据平台产品方案" />
              </Form.Item>
              <Form.Item label="分类" name="category">
                <Select options={KNOWLEDGE_CATEGORIES} />
              </Form.Item>
            </div>
            <Form.Item label="文本内容" name="text_content">
              <Input.TextArea
                data-testid="bot-knowledge-content"
                rows={7}
                placeholder="可直接粘贴制度、方案、行业资料、客户材料等文本"
              />
            </Form.Item>
            <Space wrap>
              <Button data-testid="bot-knowledge-save" icon={<SaveOutlined />} loading={knowledgeUploading} onClick={handleCreateKnowledge}>
                保存文本知识
              </Button>
              <Upload
                beforeUpload={(file) => {
                  setKnowledgeFile(file as File);
                  return false;
                }}
                maxCount={1}
                fileList={knowledgeFile ? [{ uid: '1', name: knowledgeFile.name, status: 'done' }] as any : []}
                onRemove={() => setKnowledgeFile(null)}
              >
                <Button icon={<CloudUploadOutlined />}>选择文件</Button>
              </Upload>
              <Button type="primary" loading={knowledgeUploading} onClick={handleUploadKnowledge}>上传并索引</Button>
            </Space>
          </Form>
        </WorkbenchSection>

        <WorkbenchSection title="检索测试" description="直接验证机器人能不能从知识空间找到依据。">
          <Space.Compact style={{ width: '100%' }}>
            <Input
              data-testid="bot-knowledge-search-input"
              value={knowledgeQuery}
              onChange={(event) => setKnowledgeQuery(event.target.value)}
              placeholder="输入检索问题"
            />
            <Button data-testid="bot-knowledge-search-button" type="primary" onClick={handleSearchKnowledge}>检索</Button>
          </Space.Compact>
          <EvidenceList evidence={knowledgeSearchResult} />
        </WorkbenchSection>

        <WorkbenchSection title="知识文件" description={`当前 ${knowledgeTotal} 份文件已入库。`} className="bot-span-all">
          <Table
            className="edl-table"
            rowKey="file_id"
            dataSource={knowledgeFiles}
            pagination={false}
            columns={[
              { title: '标题', dataIndex: 'title' },
              { title: '分类', dataIndex: 'category', width: 120, render: (value: string) => <Tag>{value}</Tag> },
              { title: '切片', dataIndex: 'chunk_count', width: 90 },
              { title: '上传人', dataIndex: 'uploaded_by', width: 120 },
              { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
            ]}
          />
        </WorkbenchSection>
      </div>
    );
  }

  function renderChannelsTab() {
    return (
      <WorkbenchSection title="群聊接入" description="这里管理外部群与机器人 Profile 的绑定关系；默认钉钉群来自管理中心钉钉配置。">
        <Table
          className="edl-table"
          rowKey="channel_key"
          dataSource={bindings}
          pagination={false}
          columns={[
            { title: '群聊', dataIndex: 'channel_name' },
            { title: '类型', dataIndex: 'channel_type', width: 120, render: (value: string) => <Tag color="blue">{value}</Tag> },
            { title: '绑定机器人', dataIndex: 'bot_profile_key', render: (value: string) => profiles.find((item) => item.profile_key === value)?.name || value },
            { title: '状态', dataIndex: 'status', width: 100, render: (value: string) => <Tag color={value === 'active' ? 'success' : 'default'}>{value}</Tag> },
            { title: '配置来源', dataIndex: 'binding_config', render: (value: Record<string, any>) => value?.source || '—' },
          ]}
        />
      </WorkbenchSection>
    );
  }

  function renderBroadcastTab() {
    return (
      <div className="bot-broadcast-tab">
        <WorkbenchSection title="消息群发" description="群发是受控动作；测试对话只生成待确认草稿，不直接发送外部消息。">
          {!canBroadcast && <Alert className="bot-permission-alert" type="warning" showIcon message="当前账号没有群发权限" />}
          <Form<BroadcastFormValues>
            form={broadcastForm}
            layout="vertical"
            disabled={!canBroadcast}
            initialValues={DEFAULT_BROADCAST_FORM}
          >
            <div className="bot-form-row">
              <Form.Item label="消息标题" name="title" rules={[{ required: true, message: '请输入消息标题' }, { max: 120, message: '标题不能超过120字' }]}>
                <Input data-testid="bot-broadcast-title" placeholder="例如：本周市场洞察重点提醒" maxLength={120} showCount />
              </Form.Item>
              <Form.Item label="消息类型" name="message_type">
                <Select options={MESSAGE_TYPE_OPTIONS} />
              </Form.Item>
            </div>
            <div className="bot-form-row">
              <Form.Item label="通知类别" name="notice_type"><Select options={NOTICE_TYPE_OPTIONS} /></Form.Item>
              <Form.Item label="发送范围" name="target_type"><Select disabled options={[{ value: 'configured_group', label: '当前钉钉默认群' }]} /></Form.Item>
            </div>
            <Form.Item label="消息正文" name="content" rules={[{ required: true, message: '请输入消息正文' }, { max: 5000, message: '正文不能超过5000字' }]}>
              <Input.TextArea
                data-testid="bot-broadcast-content"
                rows={6}
                maxLength={5000}
                showCount
                placeholder="输入要发送给群内成员的内容。图文排版模式支持 Markdown。"
              />
            </Form.Item>
            <div className="bot-form-actions">
              <Form.Item name="at_all" valuePropName="checked" noStyle>
                <Switch checkedChildren="@所有人" unCheckedChildren="普通发送" />
              </Form.Item>
              <Space wrap>
                <Button data-testid="bot-broadcast-save-draft" icon={<SaveOutlined />} loading={broadcastSaving} onClick={handleSaveDraft}>
                  保存草稿
                </Button>
                <Popconfirm title="确认立即群发？" description="消息会发送到当前钉钉默认群，发送结果会写入记录。" okText="确认发送" cancelText="再检查" onConfirm={handleSendNow}>
                  <Button type="primary" icon={<SendOutlined />} loading={broadcastSending}>确认发送</Button>
                </Popconfirm>
              </Space>
            </div>
          </Form>
        </WorkbenchSection>

        <WorkbenchSection
          title="发送记录"
          description="失败草稿可以重新发送。"
          action={
            <Space wrap>
              <Select
                value={broadcastStatusFilter}
                style={{ width: 132 }}
                onChange={(value) => setBroadcastStatusFilter(value)}
                options={[
                  { value: 'all', label: '全部状态' },
                  { value: 'draft', label: '草稿' },
                  { value: 'sent', label: '已发送' },
                  { value: 'failed', label: '发送失败' },
                ]}
              />
              <Button onClick={loadBroadcasts}>刷新</Button>
            </Space>
          }
        >
          <Table
            className="edl-table bot-record-table"
            rowKey="id"
            dataSource={broadcasts}
            pagination={false}
            scroll={{ x: 980 }}
            locale={{ emptyText: <Empty description="暂无群发记录" /> }}
            columns={[
              {
                title: '消息',
                dataIndex: 'title',
                width: 300,
                render: (_: string, record: BotBroadcastItem) => (
                  <div className="bot-table-title"><strong>{record.title}</strong><span>{record.content}</span></div>
                ),
              },
              {
                title: '状态',
                dataIndex: 'status',
                width: 110,
                render: (value: BotBroadcastStatus) => {
                  const meta = STATUS_META[value] || STATUS_META.draft;
                  return <Tag icon={meta.icon} color={meta.color}>{meta.label}</Tag>;
                },
              },
              { title: '收件范围', dataIndex: 'target_summary', width: 190 },
              { title: '发送时间', dataIndex: 'sent_at', width: 170, render: formatTime },
              {
                title: '结果',
                dataIndex: 'result_message',
                render: (value: string, record: BotBroadcastItem) => (
                  <Tooltip title={record.error_message || value || '暂无发送结果'}>
                    <span className={record.status === 'failed' ? 'bot-result is-error' : 'bot-result'}>{record.error_message || value || '—'}</span>
                  </Tooltip>
                ),
              },
              {
                title: '操作',
                width: 112,
                render: (_: unknown, record: BotBroadcastItem) => {
                  const canResend = canBroadcast && ['draft', 'failed'].includes(record.status);
                  if (!canResend) return <span className="bot-muted">无可用操作</span>;
                  return (
                    <Popconfirm title="确认发送这条消息？" description="消息会发送到当前钉钉默认群。" okText="发送" cancelText="取消" onConfirm={() => handleResend(record)}>
                      <Button size="small" icon={<SendOutlined />} loading={resendingId === record.id}>发送</Button>
                    </Popconfirm>
                  );
                },
              },
            ]}
          />
        </WorkbenchSection>
      </div>
    );
  }

  function renderLogsTab() {
    return (
      <div className="bot-logs-grid">
        <WorkbenchSection title="Skill 运行日志" description="每次 Skill 调用的状态、耗时和证据数量。">
          <Table
            className="edl-table"
            rowKey="run_id"
            dataSource={skillRuns}
            pagination={false}
            columns={[
              { title: 'Skill', dataIndex: 'skill_key' },
              { title: '状态', dataIndex: 'status', width: 110, render: (value: string) => <Tag color={value === 'success' ? 'success' : 'error'}>{value}</Tag> },
              { title: '证据', dataIndex: 'evidence_records', width: 90, render: (value: any[]) => value?.length || 0 },
              { title: '耗时', dataIndex: 'duration_ms', width: 100, render: (value: number) => `${value || 0} ms` },
              { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
            ]}
          />
        </WorkbenchSection>
        <WorkbenchSection title="审计日志" description="配置、测试、知识入库等关键动作。">
          <Table
            className="edl-table"
            rowKey="id"
            dataSource={auditLogs}
            pagination={false}
            columns={[
              { title: '事件', dataIndex: 'event_type' },
              { title: '机器人', dataIndex: 'profile_key' },
              { title: '操作者', dataIndex: 'actor_name', width: 120 },
              { title: '时间', dataIndex: 'created_at', width: 170, render: formatTime },
            ]}
          />
        </WorkbenchSection>
      </div>
    );
  }
};

const EvidenceList: React.FC<{ evidence: BotEvidenceRecord[] }> = ({ evidence }) => {
  if (!evidence.length) return <Empty description="暂无证据" />;
  return (
    <div className="bot-evidence-list">
      {evidence.slice(0, 8).map((item) => (
        <div className="bot-evidence" key={item.evidence_id}>
          <div>
            <strong>{item.title || item.evidence_id}</strong>
            <Tag>{item.source_type}</Tag>
          </div>
          <p>{item.snippet || item.source || '已命中证据'}</p>
          <span>{item.source || item.category || '内部数据'} {item.published_at ? `· ${item.published_at}` : ''}</span>
        </div>
      ))}
    </div>
  );
};

function formatTime(value?: string | null): string {
  if (!value) return '—';
  return dayjs(value).format('YYYY-MM-DD HH:mm');
}

export default BotCenter;
