import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyOutlined,
  SendOutlined,
  ThunderboltOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchCrawlerSources,
  createCrawlerSource,
  updateCrawlerSource,
  deleteCrawlerSource,
  fetchKeywords,
  updateKeywords,
  fetchSchedule,
  updateSchedule,
  fetchCrawlerStatus,
  fetchCrawlerRuns,
  triggerCrawler,
  triggerAllCrawlers,
  fetchLLMConfig,
  updateLLMConfig,
  testLLMConnection,
  fetchLLMStats,
  fetchPrompts,
  updatePrompt,
  fetchSystemUsers,
  createSystemUser,
  updateSystemUser,
  resetUserPassword,
  deleteSystemUser,
  fetchRoles,
  fetchOperationLogs,
  fetchAPIKeys,
  createAPIKey,
  deleteAPIKey,
  toggleAPIKey,
  fetchDingtalkConfig,
  updateDingtalkConfig,
  testDingtalk,
  fetchAipaasConfig,
  updateAipaasConfig,
  triggerAipaasSync,
  fetchSystemInfo,
  changeCurrentPassword,
  logout,
  getPermissionLabel,
  getApiErrorMessage,
  CrawlerSourceItem,
  CrawlerStatus,
  CrawlerRunLog,
  LLMConfigData,
  LLMStats,
  PromptTemplate,
  SystemUser,
  RoleDef,
  APIKeyItem,
  AipaasConfigData,
} from '@/services/api';
import { WorkbenchSection, WorkbenchStatusRail } from '@/components/workbench';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const LLMTab: React.FC = () => {
  const [config, setConfig] = useState<LLMConfigData | null>(null);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [stats, setStats] = useState<LLMStats | null>(null);
  const [testing, setTesting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(false);
  const [configForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, p, s] = await Promise.all([
        fetchLLMConfig().catch(() => null),
        fetchPrompts().catch(() => []),
        fetchLLMStats().catch(() => null),
      ]);
      setConfig(c);
      setPrompts(p);
      setStats(s);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTest = async () => {
    setTesting(true);
    try {
      const r = await testLLMConnection();
      if (r.success) message.success(r.message);
      else message.error(r.message);
    } catch (e: any) { message.error(getApiErrorMessage(e, '测试失败')); }
    finally { setTesting(false); }
  };

  const formatLatency = (ms?: number) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      await updateLLMConfig(values);
      message.success('配置已保存');
      setEditing(false);
      load();
    } catch { /* validation */ }
  };

  const handleSavePrompt = async () => {
    if (!editingPrompt) return;
    await updatePrompt(editingPrompt.scene, { template: editText });
    message.success('Prompt 已保存');
    setEditingPrompt(null);
    load();
  };

  return (
    <Spin spinning={loading}>
      {/* 模型配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><RobotOutlined /> 模型配置</h3>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={handleTest} loading={testing} size="small">测试连接</Button>
            {!editing && <Button icon={<EditOutlined />} onClick={() => { setEditing(true); configForm.setFieldsValue({ model_name: config?.model_name, api_base_url: config?.api_base_url, api_key: '', default_temperature: config?.default_temperature }); }} size="small">编辑</Button>}
          </Space>
        </div>

        {config && !editing && (
          <Descriptions size="small" bordered column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="当前模型"><Tag color="blue">{config.model_name}</Tag></Descriptions.Item>
            <Descriptions.Item label="API Base URL"><Text style={{ fontSize: 12 }}>{config.api_base_url}</Text></Descriptions.Item>
            <Descriptions.Item label="API Key">
              <Tag color={config.configured ? 'green' : 'orange'}>{config.configured ? '已配置' : '未配置'}</Tag>
              <Text style={{ fontSize: 12, marginLeft: 8 }}>{config.api_key_masked}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Temperature">{config.default_temperature}</Descriptions.Item>
          </Descriptions>
        )}

        {editing && (
          <Card size="small">
            <Form form={configForm} layout="vertical">
              <Row gutter={16}>
                <Col xs={24} md={8}>
                  <Form.Item label="模型名称" name="model_name" rules={[{ required: true }]}>
                    <Select options={[
                      { value: 'deepseek-chat', label: 'DeepSeek Chat' },
                      { value: 'deepseek-reasoner', label: 'DeepSeek Reasoner' },
                      { value: 'qwen-turbo', label: 'Qwen Turbo (通义千问)' },
                      { value: 'qwen-plus', label: 'Qwen Plus (通义千问)' },
                      { value: 'gpt-4o-mini', label: 'GPT-4o Mini (OpenAI)' },
                    ]} />
                  </Form.Item>
                </Col>
                <Col xs={24} md={10}>
                  <Form.Item label="API Base URL" name="api_base_url" rules={[{ required: true }]}>
                    <Input placeholder="https://api.deepseek.com" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={6}>
                  <Form.Item label="Temperature" name="default_temperature">
                    <Input type="number" min={0} max={1} step={0.1} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item label="API Key（留空表示不修改）" name="api_key">
                <Input.Password placeholder="留空则保留已配置 Key" />
              </Form.Item>
              <Space>
                <Button type="primary" onClick={handleSaveConfig}>保存配置</Button>
                <Button onClick={() => setEditing(false)}>取消</Button>
              </Space>
            </Form>
          </Card>
        )}

        {!config && <Empty description="LLM 配置未初始化" />}
      </div>

      {/* 调用审计 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><DatabaseOutlined /> 调用审计</h3>
          <Button icon={<ReloadOutlined />} onClick={load} size="small">刷新</Button>
        </div>
        {stats?.implemented ? (
          <>
            <div className="mgmt-llm-stats">
              <div><span>今日调用</span><b>{stats.today_calls}</b></div>
              <div><span>今日 Token</span><b>{stats.todayTokens}</b></div>
              <div><span>今日失败</span><b>{stats.todayErrors || 0}</b></div>
              <div><span>平均耗时</span><b>{formatLatency(stats.todayAvgLatencyMs)}</b></div>
              <div><span>本周调用</span><b>{stats.weekCalls}</b></div>
              <div><span>本周 Token</span><b>{stats.weekTokens}</b></div>
            </div>
            <div className="mgmt-llm-scenes">
              {Object.entries(stats.byScene || {}).length ? Object.entries(stats.byScene).map(([scene, item]) => (
                <Tag key={scene}>
                  {scene} · {item.calls} 次 · {item.tokens} token{item.errors ? ` · 失败 ${item.errors}` : ''}
                </Tag>
              )) : <Text type="secondary">暂无调用记录</Text>}
            </div>
            {!!stats.recentErrors?.length && (
              <div className="mgmt-llm-errors">
                {stats.recentErrors.map((err, index) => (
                  <Tooltip title={err.error_message || '调用失败'} key={`${err.scene}-${index}`}>
                    <Tag color="red">{err.scene} · {err.created_at ? dayjs(err.created_at).format('MM/DD HH:mm') : '未知时间'}</Tag>
                  </Tooltip>
                ))}
              </div>
            )}
          </>
        ) : (
          <Empty description={stats?.message || '暂无调用审计'} />
        )}
      </div>

      {/* Prompt 模板 */}
      <div className="mgmt-section">
        <h3>Prompt 模板管理</h3>
        <Row gutter={[12, 12]}>
          {prompts.map(p => (
            <Col key={p.scene} xs={24} md={12}>
              <Card size="small" title={<><Text strong>{p.name}</Text> <Tag style={{ marginLeft: 8 }}>{p.scene}</Tag></>}
                extra={<Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setEditingPrompt(p); setEditText(p.template); }}>编辑</Button>}>
                <Paragraph ellipsis={{ rows: 3 }} style={{ fontSize: 12, color: 'var(--ink-faint)', margin: 0 }}>
                  {p.template}
                </Paragraph>
                <div style={{ marginTop: 8 }}>
                  <Tag>温度 {p.temperature}</Tag>
                  <Tag>Max {p.max_tokens} tokens</Tag>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 编辑 Prompt Modal */}
      <Modal title={`编辑 Prompt：${editingPrompt?.name || ''}`} open={!!editingPrompt} onOk={handleSavePrompt} onCancel={() => setEditingPrompt(null)} width={700} okText="保存">
        <TextArea value={editText} onChange={e => setEditText(e.target.value)} rows={10} style={{ fontFamily: 'var(--mono)', fontSize: 13 }} />
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 3: 账号与权限
   ================================================================ */


export default LLMTab;
