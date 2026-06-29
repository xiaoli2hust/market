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
  TeamOutlined,
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

const SettingsTab: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<APIKeyItem[]>([]);
  const [dingtalk, setDingtalk] = useState<any>(null);
  const [aipaas, setAipaas] = useState<AipaasConfigData | null>(null);
  const [sysInfo, setSysInfo] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [testingDing, setTestingDing] = useState(false);
  const [syncingAipaas, setSyncingAipaas] = useState(false);
  const [dingForm] = Form.useForm();
  const [jianyuForm] = Form.useForm();
  const [aipaasForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [k, d, a, s] = await Promise.all([
        fetchAPIKeys().catch(() => []),
        fetchDingtalkConfig().catch(() => null),
        fetchAipaasConfig().catch(() => null),
        fetchSystemInfo().catch(() => null),
      ]);
      setApiKeys(k);
      setDingtalk(d);
      setAipaas(a);
      setSysInfo(s);
      if (d) {
        dingForm.setFieldsValue({
          delivery_mode: d.delivery_mode || 'webhook',
          webhook_url: d.webhook_url !== '未配置' ? d.webhook_url : '',
          secret: '',
          app_key: d.app_key || '',
          app_secret: '',
          app_id: d.app_id || '',
          agent_id: d.agent_id || '',
          robot_code: d.robot_code || '',
          open_conversation_id: d.open_conversation_id || '',
          cool_app_code: d.cool_app_code || '',
        });
        jianyuForm.setFieldsValue({
          jianyu_username: d.jianyu_username || '',
          jianyu_password: '',
          jianyu_api_key: '',
        });
      }
      if (a) {
        aipaasForm.setFieldsValue({
          base_url: a.base_url || '',
          app_id: a.app_id || '',
          sync_enabled: Boolean(a.sync_enabled),
          sync_interval_minutes: a.sync_interval_minutes || 60,
          sync_users: a.sync_users?.length ? a.sync_users : [{ user_id: '', user_name: '' }],
        });
      }
    } finally { setLoading(false); }
  }, [dingForm, jianyuForm, aipaasForm]);

  useEffect(() => { load(); }, [load]);

  const handleCreateKey = async () => {
    const name = `Key-${dayjs().format('MMDD-HHmm')}`;
    const result = await createAPIKey({ name, purpose: 'general' });
    Modal.success({
      title: 'API Key 已生成',
      content: (
        <div>
          <Paragraph type="secondary" style={{ marginBottom: 8 }}>
            完整 Key 只在本次创建后展示一次，请现在复制。
          </Paragraph>
          <Text copyable={{ text: result.key_value }} style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>
            {result.key_value}
          </Text>
        </div>
      ),
    });
    load();
  };

  const handleDeleteKey = async (id: number) => {
    await deleteAPIKey(id);
    message.success('已删除');
    load();
  };

  const handleToggleKey = async (id: number) => {
    await toggleAPIKey(id);
    message.success('Key 状态已更新');
    load();
  };

  const handleSaveDing = async () => {
    const values = await dingForm.validateFields();
    await updateDingtalkConfig({
      delivery_mode: values.delivery_mode,
      webhook_url: values.webhook_url,
      secret: values.secret,
      app_key: values.app_key,
      app_secret: values.app_secret,
      app_id: values.app_id,
      agent_id: values.agent_id,
      robot_code: values.robot_code,
      open_conversation_id: values.open_conversation_id,
      cool_app_code: values.cool_app_code,
    });
    message.success('钉钉配置已保存');
    load();
  };

  const handleSaveJianyu = async () => {
    const values = await jianyuForm.validateFields();
    await updateDingtalkConfig({
      jianyu_username: values.jianyu_username,
      jianyu_password: values.jianyu_password,
      jianyu_api_key: values.jianyu_api_key,
    });
    message.success('结构化标讯配置已保存');
    load();
  };

  const handleSaveAipaas = async () => {
    const values = await aipaasForm.validateFields();
    await updateAipaasConfig({
      base_url: values.base_url,
      app_id: values.app_id,
      sync_enabled: Boolean(values.sync_enabled),
      sync_interval_minutes: values.sync_interval_minutes,
      sync_users: (values.sync_users || []).filter((item: any) => item?.user_id && item?.user_name),
    });
    message.success('日报同步源已保存');
    load();
  };

  const handleTriggerAipaas = async () => {
    setSyncingAipaas(true);
    try {
      const result = await triggerAipaasSync({});
      const text = result?.status === 'skipped'
        ? result.message
        : `同步完成：成功 ${result?.success || 0} 人，失败 ${result?.failed || 0} 人，跳过 ${result?.skipped || 0} 人`;
      message.success(text || '同步完成');
      load();
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '同步失败'));
    } finally {
      setSyncingAipaas(false);
    }
  };

  const handleTestDing = async () => {
    setTestingDing(true);
    try {
      const r = await testDingtalk();
      if (r.success) message.success(r.message);
      else {
        Modal.error({
          title: '钉钉测试发送失败',
          content: (
            <div>
              <Paragraph style={{ marginBottom: 8 }}>{r.message}</Paragraph>
              {r.raw?.errcode !== undefined && (
                <Text type="secondary">错误码：{r.raw.errcode}</Text>
              )}
            </div>
          ),
        });
      }
    } catch (e: any) { message.error(getApiErrorMessage(e, '测试失败')); }
    finally { setTestingDing(false); }
  };

  return (
    <Spin spinning={loading}>
      {/* API Keys */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><KeyOutlined /> API Key 管理</h3>
          <Button icon={<PlusOutlined />} onClick={handleCreateKey} size="small" type="primary" danger>生成新 Key</Button>
        </div>
        {apiKeys.length === 0 ? <Empty description="暂无 API Key" /> : (
          <Table rowKey="id" size="small" dataSource={apiKeys} pagination={false}
            columns={[
              { title: '名称', dataIndex: 'name', width: 160 },
              { title: '用途', dataIndex: 'purpose', width: 100, render: (p: string) => <Tag>{p}</Tag> },
              { title: 'Key（脱敏）', dataIndex: 'key_masked', render: (k: string) => <Text style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{k}</Text> },
              { title: '状态', dataIndex: 'is_active', width: 70, render: (v: boolean) => v ? <Tag color="green">正常</Tag> : <Tag color="red">禁用</Tag> },
              { title: '操作', key: 'action', width: 120, render: (_: any, r: APIKeyItem) => (
                <Space size={4}>
                  <Button type="link" size="small" onClick={() => handleToggleKey(r.id)}>
                    {r.is_active ? '禁用' : '启用'}
                  </Button>
                  <Popconfirm title="确定删除？" onConfirm={() => handleDeleteKey(r.id)}>
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              )},
            ]}
          />
        )}
      </div>

      {/* 钉钉配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><SendOutlined /> 钉钉推送配置</h3>
          <Space>
            <Button onClick={handleTestDing} loading={testingDing} size="small">测试发送</Button>
            <Button type="primary" onClick={handleSaveDing} size="small">保存配置</Button>
          </Space>
        </div>
        <Form form={dingForm} layout="vertical">
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 8 }}>基础配置 · 钉钉机器人用于接收销售日报、推送报告和速递通知</div>
            <Space size={[6, 6]} wrap>
              <Tag color="blue">自定义机器人</Tag>
              <Tag color={dingtalk?.delivery_mode === 'openapi' ? 'purple' : 'cyan'}>{dingtalk?.delivery_mode === 'openapi' ? 'OpenAPI 发送' : 'Webhook 发送'}</Tag>
              <Tag color={dingtalk?.configured ? 'green' : 'default'}>{dingtalk?.configured ? 'Webhook 已配置' : 'Webhook 未配置'}</Tag>
              <Tag color={dingtalk?.sign_configured ? 'green' : 'orange'}>{dingtalk?.sign_configured ? '加签已配置' : '加签未配置'}</Tag>
              <Tag color={dingtalk?.receive_configured ? 'green' : 'default'}>{dingtalk?.receive_configured ? '日报接收已配置' : '日报接收未配置'}</Tag>
              <Tag color={dingtalk?.openapi_configured ? 'green' : 'default'}>{dingtalk?.openapi_configured ? 'OpenAPI 已配置' : 'OpenAPI 未配置'}</Tag>
              <Tag color="geekblue">发送保护 20 条/分钟</Tag>
            </Space>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={8}>
              <Form.Item label="发送通道" name="delivery_mode" initialValue="webhook">
                <Select
                  options={[
                    { value: 'webhook', label: 'Webhook 群机器人' },
                    { value: 'openapi', label: 'OpenAPI 应用机器人' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} md={16}>
              <Form.Item label="钉钉消息接收地址">
                <Input
                  readOnly
                  value={`${typeof window !== 'undefined' ? window.location.origin : ''}${dingtalk?.callback_path || '/api/dingtalk/robot/callback'}`}
                />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col xs={24} md={16}>
              <Form.Item label="Webhook URL" name="webhook_url">
                <Input placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="Secret（SEC 加签密钥）" name="secret">
                <Input.Password placeholder="以 SEC 开头；留空则保留已配置密钥" />
              </Form.Item>
            </Col>
          </Row>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>
              应用凭证 · Client ID/Secret 用于接收机器人消息并获取官方接口令牌
              {dingtalk?.app_configured && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
            </div>
            <Paragraph type="secondary" style={{ margin: 0, fontSize: 12 }}>
              主动推送到指定群还需要机器人编码和群会话 ID；旧应用 AgentId 只做应用身份记录，不等同于机器人编码。
            </Paragraph>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="Client ID（原 AppKey）" name="app_key">
                <Input placeholder="钉钉应用 Client ID" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="Client Secret（留空保留）" name="app_secret">
                <Input.Password placeholder="钉钉应用 Client Secret；留空则保留已配置密钥" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="应用 ID" name="app_id">
                <Input placeholder="钉钉应用 App ID" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="原企业内部应用 AgentId" name="agent_id">
                <Input placeholder="旧应用 AgentId，用于记录应用身份" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="机器人编码 RobotCode" name="robot_code">
                <Input placeholder="在应用机器人配置中查看，不是旧 AgentId" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="目标群会话 ID" name="open_conversation_id">
                <Input placeholder="openConversationId，用于主动推送到指定群" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="酷应用编码 CoolAppCode（可选）" name="cool_app_code">
                <Input placeholder="群聊酷应用编码，未使用可留空" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
        {dingtalk && (
          <div style={{ fontSize: 12 }}>
            <Text type="secondary">能力状态：</Text>
            <Space size={[4, 4]} wrap>
              {(dingtalk.capabilities || []).map((item: any) => (
                <Tag key={item.key} color={item.ready ? 'green' : 'default'}>{item.label}</Tag>
              ))}
            </Space>
          </div>
        )}
      </div>

      {/* AIPAAS 日报同步源 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><DatabaseOutlined /> 日报同步源</h3>
          <Space>
            <Button onClick={handleTriggerAipaas} loading={syncingAipaas} size="small">立即同步</Button>
            <Button type="primary" onClick={handleSaveAipaas} size="small">保存配置</Button>
          </Space>
        </div>
        <Form form={aipaasForm} layout="vertical">
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 8 }}>AIPAAS 日报聊天记录 · 作为日报周报的数据来源之一</div>
            <Space size={[6, 6]} wrap>
              <Tag color={aipaas?.base_url && aipaas?.app_id ? 'green' : 'default'}>{aipaas?.base_url && aipaas?.app_id ? '连接信息已配置' : '连接信息未配置'}</Tag>
              <Tag color={aipaas?.sync_enabled ? 'blue' : 'default'}>{aipaas?.sync_enabled ? '自动同步已开启' : '自动同步未开启'}</Tag>
              <Tag color={(aipaas?.sync_users || []).length ? 'purple' : 'default'}>{(aipaas?.sync_users || []).length} 个同步人员</Tag>
              {aipaas?.last_sync_at && <Tag color="cyan">最近同步 {dayjs(aipaas.last_sync_at).format('MM-DD HH:mm')}</Tag>}
            </Space>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="服务地址" name="base_url">
                <Input placeholder="https://aipaas.company.com" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="App ID" name="app_id">
                <Input placeholder="AIPAAS 应用 ID" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="自动同步" name="sync_enabled" valuePropName="checked">
                <Switch checkedChildren="开启" unCheckedChildren="关闭" />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="同步间隔（分钟）" name="sync_interval_minutes" initialValue={60}>
                <InputNumber min={10} max={1440} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.List name="sync_users">
            {(fields, { add, remove }) => (
              <div>
                <div className="mgmt-section-head" style={{ padding: 0, marginBottom: 8 }}>
                  <h3 style={{ fontSize: 14, margin: 0 }}><TeamOutlined /> 同步人员</h3>
                  <Button size="small" icon={<PlusOutlined />} onClick={() => add({ user_id: '', user_name: '' })}>添加人员</Button>
                </div>
                {fields.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="还没有同步人员" />}
                {fields.map((field) => (
                  <Row gutter={12} key={field.key} align="middle">
                    <Col xs={24} md={10}>
                      <Form.Item {...field} label="工号" name={[field.name, 'user_id']}>
                        <Input placeholder="例如 33342401" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={10}>
                      <Form.Item {...field} label="姓名" name={[field.name, 'user_name']}>
                        <Input placeholder="例如 张三" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={4}>
                      <Button danger type="text" icon={<DeleteOutlined />} onClick={() => remove(field.name)}>删除</Button>
                    </Col>
                  </Row>
                ))}
              </div>
            )}
          </Form.List>
        </Form>
        {aipaas?.last_sync_result && (
          <div style={{ fontSize: 12, marginTop: 8 }}>
            <Text type="secondary">最近结果：</Text>
            <Space size={[6, 6]} wrap>
              <Tag>{String(aipaas.last_sync_result.status || 'completed')}</Tag>
              {'total_users' in aipaas.last_sync_result && <Tag>人员 {String(aipaas.last_sync_result.total_users)}</Tag>}
              {'success' in aipaas.last_sync_result && <Tag color="green">成功 {String(aipaas.last_sync_result.success)}</Tag>}
              {'failed' in aipaas.last_sync_result && <Tag color="red">失败 {String(aipaas.last_sync_result.failed)}</Tag>}
              {'skipped' in aipaas.last_sync_result && <Tag color="default">跳过 {String(aipaas.last_sync_result.skipped)}</Tag>}
              {aipaas.last_sync_result.message && <Text type="secondary">{String(aipaas.last_sync_result.message)}</Text>}
            </Space>
          </div>
        )}
      </div>

      {/* 结构化标讯数据源配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><FileSearchOutlined /> 结构化标讯数据源配置</h3>
          <Button type="primary" onClick={handleSaveJianyu} size="small">保存配置</Button>
        </div>
        <Form form={jianyuForm} layout="vertical">
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>
              标讯采集 · 数据源账号与结构化数据 Key
              {dingtalk?.jianyu_configured && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
              {dingtalk?.jianyu_api_key_masked && <Tag color="blue" style={{ marginLeft: 8 }}>Key {dingtalk.jianyu_api_key_masked}</Tag>}
            </div>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="手机号/账号" name="jianyu_username">
                <Input placeholder="数据源登录手机号" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="登录密码" name="jianyu_password">
                <Input.Password placeholder="留空则保留已配置密码" />
              </Form.Item>
            </Col>
            <Col xs={24}>
              <Form.Item label="结构化数据 Key" name="jianyu_api_key">
                <Input.Password placeholder="留空则保留已配置 Key；未配置时可用账号密码自动发现启用规则" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </div>

      {/* 系统信息 */}
      {sysInfo && (
        <div className="mgmt-section">
          <h3><ApiOutlined /> 系统信息</h3>
          <Descriptions size="small" bordered column={{ xs: 1, md: 2 }}>
            <Descriptions.Item label="版本">v{sysInfo.version}</Descriptions.Item>
            <Descriptions.Item label="LLM 模型">
              {sysInfo.llm_model}
              {sysInfo.llm_config_source && <Tag style={{ marginLeft: 8 }}>{sysInfo.llm_config_source === 'management' ? '管理中心配置' : '启动配置'}</Tag>}
            </Descriptions.Item>
            {Object.entries(sysInfo.data_stats || {}).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
            ))}
          </Descriptions>
        </div>
      )}
    </Spin>
  );
};


export default SettingsTab;
