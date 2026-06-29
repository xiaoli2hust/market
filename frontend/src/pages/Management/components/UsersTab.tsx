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

const UsersTab: React.FC = () => {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [total, setTotal] = useState(0);
  const [roles, setRoles] = useState<RoleDef[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [addVisible, setAddVisible] = useState(false);
  const [resetVisible, setResetVisible] = useState(false);
  const [selfPwdVisible, setSelfPwdVisible] = useState(false);
  const [resetUserId, setResetUserId] = useState<number>(0);
  const [form] = Form.useForm();
  const [resetForm] = Form.useForm();
  const [selfPwdForm] = Form.useForm();

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

  const handleChangeOwnPassword = async () => {
    try {
      const values = await selfPwdForm.validateFields();
      if (values.new_password !== values.confirm_password) {
        message.error('两次输入的新密码不一致');
        return;
      }
      await changeCurrentPassword({
        current_password: values.current_password,
        new_password: values.new_password,
      });
      message.success('密码已修改，请重新登录');
      setSelfPwdVisible(false);
      selfPwdForm.resetFields();
      await logout();
      window.location.href = '/user/login';
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.data?.detail || e?.message || '密码修改失败');
    }
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
      <div className="mgmt-section">
        <div className="mgmt-section-head">
          <h3><SafetyOutlined /> 当前账号安全</h3>
          <Button size="small" onClick={() => setSelfPwdVisible(true)}>
            修改我的密码
          </Button>
        </div>
        <Text type="secondary" style={{ fontSize: 12 }}>
          密码修改后需要重新登录，防止旧登录态继续使用。
        </Text>
      </div>

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
                    <Space wrap size={4}>{r.permissions.map(p => <Tag key={p} style={{ fontSize: 10 }}>{getPermissionLabel(p)}</Tag>)}</Space>
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
          <Form.Item label="密码" name="password" rules={[{ required: true, min: 8, message: '至少8位' }]}><Input.Password /></Form.Item>
          <Form.Item label="角色" name="role" initialValue="viewer" rules={[{ required: true }]}>
            <Select options={roles.map(r => ({ value: r.key, label: r.label }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 重置密码 Modal */}
      <Modal title="重置密码" open={resetVisible} onOk={handleReset} onCancel={() => setResetVisible(false)} okText="确认重置">
        <Form form={resetForm} layout="vertical">
          <Form.Item label="新密码" name="password" rules={[{ required: true, min: 8, message: '至少8位' }]}><Input.Password placeholder="输入新密码" /></Form.Item>
        </Form>
      </Modal>

      <Modal
        title="修改我的密码"
        open={selfPwdVisible}
        onOk={handleChangeOwnPassword}
        onCancel={() => setSelfPwdVisible(false)}
        okText="确认修改"
      >
        <Form form={selfPwdForm} layout="vertical">
          <Form.Item label="当前密码" name="current_password" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item label="新密码" name="new_password" rules={[{ required: true, min: 8, message: '至少8位' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item label="确认新密码" name="confirm_password" rules={[{ required: true, message: '请再次输入新密码' }]}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </Spin>
  );
};

/* ================================================================
   Tab 4: 接口与密钥
   ================================================================ */


export default UsersTab;
