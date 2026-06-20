import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
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
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  CloudServerOutlined,
  DatabaseOutlined,
  DeleteOutlined,
  EditOutlined,
  KeyOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  SafetyOutlined,
  SendOutlined,
  SettingOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  FileSearchOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchCrawlerSources,
  createCrawlerSource,
  deleteCrawlerSource,
  fetchKeywords,
  updateKeywords,
  fetchSchedule,
  fetchCrawlerStatus,
  triggerAllCrawlers,
  fetchLLMConfig,
  updateLLMConfig,
  testLLMConnection,
  fetchPrompts,
  updatePrompt,
  fetchLLMStats,
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
  fetchDingtalkConfig,
  updateDingtalkConfig,
  testDingtalk,
  fetchSystemInfo,
  CrawlerSourceItem,
  CrawlerStatus,
  LLMConfigData,
  PromptTemplate,
  SystemUser,
  RoleDef,
  APIKeyItem,
} from '@/services/api';
import './management.less';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const CATEGORY_LABELS: Record<string, { label: string; color: string }> = {
  news: { label: '市场动态', color: '#1890ff' },
  competitor: { label: '竞对监控', color: '#fa8c16' },
  ai: { label: 'AI资讯', color: '#722ed1' },
  bidding: { label: '标讯信息', color: '#f5222d' },
};

const Management: React.FC = () => {
  const [tab, setTab] = useState('crawler');

  return (
    <div className="mgmt">
      <div className="mgmt-headline edl-rise edl-rise-1">
        <div>
          <div className="edl-eyebrow">Command Center · 管理中心</div>
          <Title className="mgmt-title" level={1}>
            管理<span className="accent">中心</span>
          </Title>
          <div className="mgmt-sub">
            爬虫配置 · 大模型工作台 · 账号权限 · 接口密钥
          </div>
        </div>
      </div>
      <hr className="edl-rule-strong" />

      <Tabs
        activeKey={tab}
        onChange={setTab}
        className="mgmt-tabs edl-rise edl-rise-2"
        items={[
          { key: 'crawler', label: <span><CloudServerOutlined /> 爬虫管理</span>, children: <CrawlerTab /> },
          { key: 'llm', label: <span><RobotOutlined /> 大模型工作台</span>, children: <LLMTab /> },
          { key: 'users', label: <span><TeamOutlined /> 账号与权限</span>, children: <UsersTab /> },
          { key: 'settings', label: <span><SettingOutlined /> 接口与密钥</span>, children: <SettingsTab /> },
        ]}
      />
    </div>
  );
};

/* ================================================================
   Tab 1: 爬虫管理
   ================================================================ */

// 标讯关键词配置（与后端 crawlers/config.py 同步）
const BIDDING_KEYWORDS_CONFIG = {
  search: {
    label: '搜索关键词',
    desc: '在剑鱼网实际搜索时使用的关键词（精选高频词）',
    toG_公安: ['智慧公安','智慧警务','公安局信息化','情指行','110接处警','视频监控 公安','雪亮工程','公安大数据','警用地理','天网工程'],
    toG_政数: ['数字政府','一网统管','一网通办','智慧城市','城市大脑','政数局','数据局','数字孪生','实景三维','自然资源信息化','时空大数据'],
    toB_零售: ['售后服务 信息化','上门服务 系统','物流配送 系统','零售连锁 数字化','工单管理'],
    toB_金融: ['银行 数字化转型','银行 数据治理','保险 反欺诈','农信社 信息化','金融 风控 大数据'],
    toB_智驾: ['自动驾驶 地图','高精地图','智能驾驶 数据','车路协同','智驾 采集'],
  },
  scoring: {
    label: '评分关键词',
    desc: '采集到标讯后，用于匹配评分的业务关键词（全面覆盖）',
    toG_公安: '实时警情定位、网格绘制、网格化管理、反诈、一张图、情指行、地址画像、地址服务、地址治理、地址标准化、地址解析、地址匹配、地理编码、地址库、标准地址、一标三实、二维码门牌、地址采集、地址清洗、地址关联、地址可视化、地址大数据、地址核采、地址核验、地址引擎、警情定位、110、接处警、智能体、AGENT、PGIS、警用GIS、合成作战、指挥调度、视频侦查、智能研判、预警、布控',
    toG_政数: '时空大数据、地址、标准地址、地址核采、地址采集、地址治理、数据更新、数据运营、城市大脑、市域社会治理、一网统管、一网通办、二维码门牌、一标三实、实有人口、BIM、实景三维、分层分户、地理实体、数字孪生平台、电子地图、二标四实、人口地址、数据采集、智能体、AGENT、数字孪生、CIM、网格化管理、社会治理、政务数据、数据共享',
    toB_零售: '配送调度、智能派单、履约管理、售后管理、上门服务管理、工单管理、服务时效、服务覆盖、网点管理、工程师管理、地址标准化、地址治理、非标地址、地址解析、地址校验、地理编码、空间数据治理、区域运营、网格化管理、业务可视化、经营一张图、运营态势感知、门店管理、会员管理、物流配送、供应链管理、路径规划',
    toB_金融: '地址标准化、地址大数据、地址核验、地址清洗、地址匹配、语义地址、金融地图、位置智能、GIS服务、地图API、轨迹纠偏、逆地理编码、定位服务、路径规划、企业大数据、时空大数据、位置大数据、数据融合、数据治理、企业画像、数字孪生、AOI地图数据、线下巡检、信息稽核、经营场所验证、贷后监控、风险识别、反欺诈调查、网点选址、商圈分析、客户分布、精准营销、网点效能评价、移动展业、客户画像、地图可视化、数据可视化、私有化部署、API接口',
    toB_智驾: '合规采集、数据采集、道路信息采集、采集司机、采集管理、采集备案、跟车采集、合规安全员、数据标注、点云建图、高精地图制作、高精地图建图、高精地图制图、智驾地图制作、合规云、数据合规、合规托管、合规服务、合规咨询、保密机房、数据脱敏脱密、数据安全保护、点云、激光雷达、仿真测试',
  },
};

const DIRECTION_META: Record<string, { label: string; color: string; icon: string }> = {
  toG_公安: { label: 'toG · 公安', color: '#f5222d', icon: '🚔' },
  toG_政数: { label: 'toG · 政数', color: '#1890ff', icon: '🏛️' },
  toB_零售: { label: 'toB · 零售', color: '#fa8c16', icon: '🛒' },
  toB_金融: { label: 'toB · 金融', color: '#52c41a', icon: '🏦' },
  toB_智驾: { label: 'toB · 智驾', color: '#722ed1', icon: '🚗' },
};

const CrawlerTab: React.FC = () => {
  const [sources, setSources] = useState<CrawlerSourceItem[]>([]);
  const [keywords, setKeywords] = useState<{ category: string; keywords: string[] }[]>([]);
  const [crawlerStatus, setCrawlerStatus] = useState<CrawlerStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [crawling, setCrawling] = useState<string | null>(null);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [newSource, setNewSource] = useState({ category: 'news', name: '', url: '' });
  const [keywordTab, setKeywordTab] = useState('bidding');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, k, cs] = await Promise.all([
        fetchCrawlerSources().catch(() => []),
        fetchKeywords().catch(() => []),
        fetchCrawlerStatus().catch(() => []),
      ]);
      setSources(s);
      setKeywords(k);
      setCrawlerStatus(cs);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAddSource = async () => {
    if (!newSource.name || !newSource.url) { message.warning('请填写名称和URL'); return; }
    await createCrawlerSource(newSource);
    message.success('添加成功');
    setAddModalVisible(false);
    setNewSource({ category: 'news', name: '', url: '' });
    load();
  };

  const handleDeleteSource = async (id: number) => {
    await deleteCrawlerSource(id);
    message.success('已删除');
    load();
  };

  const handleRunCrawler = async (name: string) => {
    setCrawling(name);
    try {
      const resp = await fetch(`/api/crawlers/${name}/run`, { method: 'POST', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' } });
      const result = await resp.json();
      message.success(result.message || `采集完成：新增 ${result.new_saved} 条`);
      load();
    } catch { message.error('采集失败'); }
    finally { setCrawling(null); }
  };

  const handleCrawlAll = async () => {
    setCrawling('all');
    try {
      const results = await triggerAllCrawlers();
      const totalNew = results.reduce((s: number, r: any) => s + r.new_saved, 0);
      message.success(`全部采集完成：新增 ${totalNew} 条`);
      load();
    } catch { message.error('采集失败'); }
    finally { setCrawling(null); }
  };

  const handleSaveKeywords = async (category: string, text: string) => {
    const kw = text.split(/[,，\n]/).map(s => s.trim()).filter(Boolean);
    await updateKeywords(category, kw);
    message.success('关键词已保存');
    load();
  };

  // 标讯统计
  const biddingStatus = crawlerStatus.find(c => c.name === 'bidding');

  return (
    <Spin spinning={loading}>
      {/* 爬虫状态卡片 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><RobotOutlined /> 采集引擎</h3>
          <Button type="primary" danger icon={<ThunderboltOutlined />} loading={crawling === 'all'} onClick={handleCrawlAll} size="small">
            一键全部采集
          </Button>
        </div>
        <Row gutter={[12, 12]}>
          {crawlerStatus.map(cs => {
            const isBidding = cs.name === 'bidding';
            const isRunning = crawling === cs.name;
            return (
              <Col key={cs.name} xs={12} md={6}>
                <Card size="small" className="mgmt-mini-card" style={{ borderLeft: `3px solid ${CATEGORY_LABELS[cs.category]?.color || '#999'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className={`mgmt-dot ${cs.status === 'running' || isRunning ? 'is-running' : ''}`} />
                      <Text strong style={{ fontSize: 13 }}>{cs.label}</Text>
                    </div>
                    <Button
                      type="link"
                      size="small"
                      loading={isRunning}
                      onClick={() => handleRunCrawler(cs.name)}
                      style={{ padding: 0, fontSize: 12 }}
                    >
                      {isRunning ? '采集中...' : '采集'}
                    </Button>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      已采集 <Text strong style={{ fontSize: 16 }}>{cs.total_collected}</Text> 条
                    </Text>
                    {isBidding && biddingStatus?.last_run_at && (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {dayjs(biddingStatus.last_run_at).format('MM/DD HH:mm')}
                      </Text>
                    )}
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>
      </div>

      {/* 标讯关键词配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><FileSearchOutlined /> 标讯关键词配置</h3>
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 {Object.values(BIDDING_KEYWORDS_CONFIG.search).flat().length} 个搜索词 · {Object.values(BIDDING_KEYWORDS_CONFIG.scoring).reduce((s: number, v: string) => s + (v as string).split(/[,，]/).filter(Boolean).length, 0)} 个评分词
          </Text>
        </div>

        <Tabs
          activeKey={keywordTab}
          onChange={setKeywordTab}
          size="small"
          items={[
            {
              key: 'bidding',
              label: <span><FileSearchOutlined /> 标讯关键词</span>,
              children: (
                <div>
                  <div style={{ marginBottom: 16 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      按 5 个业务方向组织：搜索关键词用于在剑鱼网搜索，评分关键词用于采集后的匹配打分。
                    </Text>
                  </div>

                  {/* 搜索关键词 */}
                  <div style={{ marginBottom: 20 }}>
                    <div style={{ marginBottom: 8, fontWeight: 600, fontSize: 13 }}>
                      🔍 搜索关键词（在剑鱼网搜索时使用）
                    </div>
                    <Row gutter={[12, 12]}>
                      {Object.entries(BIDDING_KEYWORDS_CONFIG.search).map(([dir, kws]) => {
                        const meta = DIRECTION_META[dir];
                        if (!meta) return null;
                        return (
                          <Col key={dir} xs={24} md={12} lg={8}>
                            <div style={{ padding: '10px 14px', background: '#fafafa', borderRadius: 8, borderLeft: `3px solid ${meta.color}`, height: '100%' }}>
                              <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 12, color: meta.color }}>
                                {meta.icon} {meta.label}
                                <span style={{ float: 'right', fontWeight: 400, color: '#999' }}>{(kws as string[]).length} 个</span>
                              </div>
                              <div style={{ fontSize: 12, lineHeight: '1.8', color: '#555' }}>
                                {(kws as string[]).map((kw: string, i: number) => (
                                  <Tag key={i} style={{ margin: '1px 2px', fontSize: 11 }}>{kw}</Tag>
                                ))}
                              </div>
                            </div>
                          </Col>
                        );
                      })}
                    </Row>
                  </div>

                  {/* 评分关键词 */}
                  <div>
                    <div style={{ marginBottom: 8, fontWeight: 600, fontSize: 13 }}>
                      📊 评分关键词（采集后匹配打分使用）
                    </div>
                    <Row gutter={[12, 12]}>
                      {Object.entries(BIDDING_KEYWORDS_CONFIG.scoring).map(([dir, kwStr]) => {
                        const meta = DIRECTION_META[dir];
                        if (!meta) return null;
                        const kwList = (kwStr as string).split(/[,，]/).map(s => s.trim()).filter(Boolean);
                        return (
                          <Col key={dir} xs={24} md={12}>
                            <div style={{ padding: '10px 14px', background: '#fafafa', borderRadius: 8, borderLeft: `3px solid ${meta.color}`, height: '100%' }}>
                              <div style={{ marginBottom: 6, fontWeight: 600, fontSize: 12, color: meta.color }}>
                                {meta.icon} {meta.label}
                                <span style={{ float: 'right', fontWeight: 400, color: '#999' }}>{kwList.length} 个</span>
                              </div>
                              <div style={{ fontSize: 12, lineHeight: '1.8', color: '#555' }}>
                                {kwList.slice(0, 20).map((kw, i) => (
                                  <Tag key={i} style={{ margin: '1px 2px', fontSize: 11 }}>{kw}</Tag>
                                ))}
                                {kwList.length > 20 && (
                                  <Tag style={{ margin: '1px 2px', fontSize: 11, color: '#999' }}>+{kwList.length - 20} 个</Tag>
                                )}
                              </div>
                            </div>
                          </Col>
                        );
                      })}
                    </Row>
                  </div>
                </div>
              ),
            },
            {
              key: 'other',
              label: <span><GlobalOutlined /> 其他爬虫关键词</span>,
              children: (
                <div>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
                    市场动态、竞对监控、AI 资讯的关键词配置（逗号分隔，修改后自动保存）
                  </Text>
                  <Row gutter={[16, 16]}>
                    {keywords.filter(kw => kw.category !== 'bidding').map(kw => (
                      <Col key={kw.category} xs={24} md={12}>
                        <Card size="small" title={<Tag color={CATEGORY_LABELS[kw.category]?.color}>{CATEGORY_LABELS[kw.category]?.label || kw.category}</Tag>}>
                          <TextArea
                            defaultValue={kw.keywords.join(', ')}
                            rows={3}
                            placeholder="关键词用逗号分隔"
                            onBlur={(e) => handleSaveKeywords(kw.category, e.target.value)}
                          />
                        </Card>
                      </Col>
                    ))}
                  </Row>
                </div>
              ),
            },
          ]}
        />
      </div>

      {/* 目标站点管理 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><DatabaseOutlined /> 目标站点管理</h3>
          <Button icon={<PlusOutlined />} onClick={() => setAddModalVisible(true)} size="small">添加站点</Button>
        </div>
        <Table
          rowKey="id"
          size="small"
          dataSource={sources}
          pagination={false}
          columns={[
            { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color={CATEGORY_LABELS[c]?.color}>{CATEGORY_LABELS[c]?.label || c}</Tag> },
            { title: '名称', dataIndex: 'name', width: 150, render: (t: string) => <Text strong>{t}</Text> },
            { title: 'URL', dataIndex: 'url', ellipsis: true, render: (u: string) => <Text copyable style={{ fontSize: 12 }}>{u}</Text> },
            { title: '状态', dataIndex: 'is_active', width: 70, render: (v: boolean) => v ? <Tag color="green">启用</Tag> : <Tag>禁用</Tag> },
            { title: '', key: 'action', width: 60, render: (_: any, r: CrawlerSourceItem) => (
              <Popconfirm title="确定删除？" onConfirm={() => handleDeleteSource(r.id)}>
                <Button type="text" danger size="small" icon={<DeleteOutlined />} />
              </Popconfirm>
            )},
          ]}
        />
      </div>

      {/* 添加站点 Modal */}
      <Modal title="添加目标站点" open={addModalVisible} onOk={handleAddSource} onCancel={() => setAddModalVisible(false)} okText="添加">
        <Form layout="vertical">
          <Form.Item label="分类">
            <Select value={newSource.category} onChange={v => setNewSource(s => ({ ...s, category: v }))}
              options={Object.entries(CATEGORY_LABELS).map(([k, v]) => ({ value: k, label: v.label }))} />
          </Form.Item>
          <Form.Item label="名称" required>
            <Input value={newSource.name} onChange={e => setNewSource(s => ({ ...s, name: e.target.value }))} placeholder="如：自然资源部" />
          </Form.Item>
          <Form.Item label="URL" required>
            <Input value={newSource.url} onChange={e => setNewSource(s => ({ ...s, url: e.target.value }))} placeholder="https://..." />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 2: 大模型工作台
   ================================================================ */

const LLMTab: React.FC = () => {
  const [config, setConfig] = useState<LLMConfigData | null>(null);
  const [prompts, setPrompts] = useState<PromptTemplate[]>([]);
  const [testing, setTesting] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(null);
  const [editText, setEditText] = useState('');
  const [loading, setLoading] = useState(false);
  const [configForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, p] = await Promise.all([
        fetchLLMConfig().catch(() => null),
        fetchPrompts().catch(() => []),
      ]);
      setConfig(c);
      setPrompts(p);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleTest = async () => {
    setTesting(true);
    try {
      const r = await testLLMConnection();
      if (r.success) message.success(r.message);
      else message.error(r.message);
    } catch { message.error('测试失败'); }
    finally { setTesting(false); }
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
                <Input.Password placeholder="sk-..." />
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

const UsersTab: React.FC = () => {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [total, setTotal] = useState(0);
  const [roles, setRoles] = useState<RoleDef[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [addVisible, setAddVisible] = useState(false);
  const [resetVisible, setResetVisible] = useState(false);
  const [resetUserId, setResetUserId] = useState<number>(0);
  const [form] = Form.useForm();
  const [resetForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [u, r, l] = await Promise.all([
        fetchSystemUsers().catch(() => ({ total: 0, items: [] })),
        fetchRoles().catch(() => []),
        fetchOperationLogs().catch(() => ({ total: 0, items: [] })),
      ]);
      setUsers(u.items);
      setTotal(u.total);
      setRoles(r);
      setLogs(l.items);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createSystemUser(values);
      message.success('用户已创建');
      setAddVisible(false);
      form.resetFields();
      load();
    } catch { /* validation error */ }
  };

  const handleReset = async () => {
    try {
      const { password } = await resetForm.validateFields();
      await resetUserPassword(resetUserId, password);
      message.success('密码已重置');
      setResetVisible(false);
      resetForm.resetFields();
    } catch { /* validation error */ }
  };

  const handleDelete = async (id: number) => {
    await deleteSystemUser(id);
    message.success('已删除');
    load();
  };

  const handleToggleActive = async (user: SystemUser) => {
    await updateSystemUser(user.id, { is_active: !user.is_active });
    message.success(user.is_active ? '已禁用' : '已启用');
    load();
  };

  return (
    <Spin spinning={loading}>
      {/* 用户列表 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><TeamOutlined /> 用户列表 <Tag>{total}</Tag></h3>
          <Button icon={<PlusOutlined />} onClick={() => setAddVisible(true)} size="small" type="primary" danger>新增用户</Button>
        </div>
        <Table rowKey="id" size="small" dataSource={users} pagination={false}
          columns={[
            { title: '用户名', dataIndex: 'username', width: 120, render: (t: string, r: SystemUser) => <><Text strong>{t}</Text><br /><Text type="secondary" style={{ fontSize: 11 }}>{r.display_name}</Text></> },
            { title: '角色', dataIndex: 'role_label', width: 110, render: (l: string, r: SystemUser) => <Tag color={r.role === 'super_admin' ? 'red' : r.role === 'admin' ? 'blue' : 'default'}>{l}</Tag> },
            { title: '状态', dataIndex: 'is_active', width: 80, render: (v: boolean) => v ? <Tag color="green">正常</Tag> : <Tag color="red">禁用</Tag> },
            { title: '创建时间', dataIndex: 'created_at', width: 120, render: (t: string) => <span className="edl-mono" style={{ fontSize: 11 }}>{t ? dayjs(t).format('YYYY·MM·DD') : '—'}</span> },
            { title: '操作', key: 'action', width: 180, render: (_: any, r: SystemUser) => (
              <Space size={4}>
                <Button type="link" size="small" onClick={() => { setResetUserId(r.id); setResetVisible(true); }}>重置密码</Button>
                <Button type="link" size="small" onClick={() => handleToggleActive(r)}>{r.is_active ? '禁用' : '启用'}</Button>
                {r.username !== 'admin' && <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}><Button type="link" size="small" danger>删除</Button></Popconfirm>}
              </Space>
            )},
          ]}
        />
      </div>

      {/* 角色定义 */}
      <div className="mgmt-section">
        <h3><SafetyOutlined /> 角色权限矩阵</h3>
        <Row gutter={[12, 12]}>
          {roles.map(r => (
            <Col key={r.key} xs={24} md={8}>
              <Card size="small" title={<Tag color={r.key === 'super_admin' ? 'red' : r.key === 'admin' ? 'blue' : 'default'}>{r.label}</Tag>}>
                <div style={{ fontSize: 12, color: 'var(--ink-faint)' }}>
                  {r.permissions.includes('*') ? (
                    <Text type="success">全部权限</Text>
                  ) : (
                    <Space wrap size={4}>{r.permissions.map(p => <Tag key={p} style={{ fontSize: 10 }}>{p}</Tag>)}</Space>
                  )}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 操作日志 */}
      <div className="mgmt-section">
        <h3>操作日志</h3>
        {logs.length === 0 ? <Empty description="暂无日志" /> : (
          <Table rowKey="id" size="small" dataSource={logs} pagination={{ pageSize: 10 }}
            columns={[
              { title: '操作人', dataIndex: 'username', width: 100 },
              { title: '操作', dataIndex: 'action', width: 120 },
              { title: '目标', dataIndex: 'target', ellipsis: true },
              { title: '时间', dataIndex: 'created_at', width: 140, render: (t: string) => <span className="edl-mono" style={{ fontSize: 11 }}>{t ? dayjs(t).format('MM·DD HH:mm') : '—'}</span> },
            ]}
          />
        )}
      </div>

      {/* 新增用户 Modal */}
      <Modal title="新增用户" open={addVisible} onOk={handleCreate} onCancel={() => setAddVisible(false)} okText="创建">
        <Form form={form} layout="vertical">
          <Form.Item label="用户名" name="username" rules={[{ required: true }]}><Input placeholder="英文用户名" /></Form.Item>
          <Form.Item label="显示名称" name="display_name"><Input placeholder="中文名" /></Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, min: 6, message: '至少6位' }]}><Input.Password /></Form.Item>
          <Form.Item label="角色" name="role" initialValue="viewer" rules={[{ required: true }]}>
            <Select options={roles.map(r => ({ value: r.key, label: r.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 重置密码 Modal */}
      <Modal title="重置密码" open={resetVisible} onOk={handleReset} onCancel={() => setResetVisible(false)} okText="确认重置">
        <Form form={resetForm} layout="vertical">
          <Form.Item label="新密码" name="password" rules={[{ required: true, min: 6, message: '至少6位' }]}><Input.Password placeholder="输入新密码" /></Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 4: 接口与密钥
   ================================================================ */

const SettingsTab: React.FC = () => {
  const [apiKeys, setApiKeys] = useState<APIKeyItem[]>([]);
  const [dingtalk, setDingtalk] = useState<any>(null);
  const [sysInfo, setSysInfo] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [testingDing, setTestingDing] = useState(false);
  const [dingForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [k, d, s] = await Promise.all([
        fetchAPIKeys().catch(() => []),
        fetchDingtalkConfig().catch(() => null),
        fetchSystemInfo().catch(() => null),
      ]);
      setApiKeys(k);
      setDingtalk(d);
      setSysInfo(s);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreateKey = async () => {
    const name = `Key-${dayjs().format('MMDD-HHmm')}`;
    const result = await createAPIKey({ name, purpose: 'general' });
    message.success(`新 Key 已生成：${result.key_value?.slice(0, 16)}...`);
    load();
  };

  const handleDeleteKey = async (id: number) => {
    await deleteAPIKey(id);
    message.success('已删除');
    load();
  };

  const handleSaveDing = async () => {
    const values = await dingForm.validateFields();
    await updateDingtalkConfig({
      webhook_url: values.webhook_url,
      secret: values.secret,
      app_key: values.app_key,
      app_secret: values.app_secret,
    });
    message.success('钉钉配置已保存');
    load();
  };

  const handleTestDing = async () => {
    setTestingDing(true);
    try {
      const r = await testDingtalk();
      if (r.success) message.success(r.message);
      else message.error(r.message);
    } catch { message.error('测试失败'); }
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
              { title: 'Key（脱敏）', dataIndex: 'key_masked', render: (k: string) => <Text copyable style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{k}</Text> },
              { title: '状态', dataIndex: 'is_active', width: 70, render: (v: boolean) => v ? <Tag color="green">正常</Tag> : <Tag color="red">禁用</Tag> },
              { title: '', key: 'action', width: 60, render: (_: any, r: APIKeyItem) => (
                <Popconfirm title="确定删除？" onConfirm={() => handleDeleteKey(r.id)}>
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                </Popconfirm>
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
        <Form form={dingForm} layout="vertical" initialValues={{
          webhook_url: dingtalk?.webhook_url !== '未配置' ? dingtalk?.webhook_url : '',
          secret: '',
          app_key: dingtalk?.app_key || '',
          app_secret: '',
        }}>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>基础配置 · 自定义机器人 Webhook（用于发送消息）</div>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={16}>
              <Form.Item label="Webhook URL" name="webhook_url">
                <Input placeholder="https://oapi.dingtalk.com/robot/send?access_token=..." />
              </Form.Item>
            </Col>
            <Col xs={24} md={8}>
              <Form.Item label="Secret（加签密钥）" name="secret">
                <Input.Password placeholder="SEC..." />
              </Form.Item>
            </Col>
          </Row>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>
              高级配置 · 企业内部应用（可选，用于速递长图上传）
              {dingtalk?.app_configured && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
            </div>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="AppKey" name="app_key">
                <Input placeholder="企业内部应用 AppKey" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="AppSecret" name="app_secret">
                <Input.Password placeholder="企业内部应用 AppSecret" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
        {dingtalk && <Text type="secondary" style={{ fontSize: 12 }}>当前状态：{dingtalk.configured ? <Tag color="green">Webhook 已配置</Tag> : <Tag>未配置</Tag>}</Text>}
      </div>

      {/* 剑鱼标讯配置 */}
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><FileSearchOutlined /> 剑鱼标讯配置</h3>
          <Button type="primary" onClick={handleSaveDing} size="small">保存配置</Button>
        </div>
        <Form form={dingForm} layout="vertical" initialValues={{
          jianyu_username: dingtalk?.jianyu_username || '',
          jianyu_password: '',
        }}>
          <div style={{ marginBottom: 12, padding: '8px 12px', background: 'var(--paper)', borderRadius: 6, border: '1px dashed var(--border)' }}>
            <div style={{ fontSize: 12, color: 'var(--ink-faint)', marginBottom: 4 }}>
              标讯采集 · 剑鱼网 VIP 账号（用于自动登录采集标讯数据）
              {dingtalk?.jianyu_configured && <Tag color="green" style={{ marginLeft: 8 }}>已配置</Tag>}
            </div>
          </div>
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Form.Item label="手机号/账号" name="jianyu_username">
                <Input placeholder="剑鱼网登录手机号" />
              </Form.Item>
            </Col>
            <Col xs={24} md={12}>
              <Form.Item label="密码" name="jianyu_password">
                <Input.Password placeholder="剑鱼网登录密码" />
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
            <Descriptions.Item label="LLM 模型">{sysInfo.llm_model}</Descriptions.Item>
            {Object.entries(sysInfo.data_stats || {}).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>{String(v)}</Descriptions.Item>
            ))}
          </Descriptions>
        </div>
      )}
    </Spin>
  );
};

export default Management;
