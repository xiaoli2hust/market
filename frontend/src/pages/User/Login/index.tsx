import React, { useState } from 'react';
import { history } from '@@/exports';
import { Form, Input, Button, message } from 'antd';
import dayjs from 'dayjs';
import { login, setAuth } from '@/services/api';
import './login.less';

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const result = await login(values);
      setAuth(result.user);
      if (result.user?.must_change_password) {
        message.warning('当前仍在使用默认管理员密码，请先到管理中心修改');
        history.replace('/management?tab=users');
        return;
      }
      message.success('登录成功');
      history.replace('/dashboard');
    } catch (e: any) {
      message.error(e?.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      {/* 左：产品刊头 */}
      <aside className="login-left">
        <div className="login-eyebrow edl-eyebrow">日报周报 · 市场洞察 · 商机推进 · 管理复盘</div>
        <div className="login-stamp">№ {dayjs().format('YYYYMMDD')}</div>

        <h1 className="login-title">
          <span className="brand">Market</span>
          <span className="zh">数据采集中心</span>
          <span className="en">Data Collection Center</span>
        </h1>

        <div className="login-quote">
          <blockquote>
            "采集，是把外部信号变成可用的数据资产。"
          </blockquote>
          <cite>— Market Data Collection Center</cite>
        </div>

        <div className="login-features">
          <div className="login-feature">
            <span className="feat-num">01</span>
            <div>
              <div className="feat-zh">部门日报周报</div>
              <div className="feat-en edl-eyebrow">Team briefing</div>
            </div>
          </div>
          <div className="login-feature">
            <span className="feat-num">02</span>
            <div>
              <div className="feat-zh">外部信号研判</div>
              <div className="feat-en edl-eyebrow">Signal discovery</div>
            </div>
          </div>
          <div className="login-feature">
            <span className="feat-num">03</span>
            <div>
              <div className="feat-zh">商机推进预测</div>
              <div className="feat-en edl-eyebrow">Pipeline forecast</div>
            </div>
          </div>
        </div>

        <div className="login-decor-cn">发现 · 确认 · 预测</div>
      </aside>

      {/* 右：登录表单 */}
      <section className="login-right">
        <div className="login-form-wrap">
          <div className="edl-eyebrow">Sign In · 凭证登录</div>
          <h2 className="login-form-title">
            进入<span className="seal">采集中心</span>
          </h2>

          <Form layout="vertical" onFinish={handleSubmit} size="large" requiredMark={false}>
            <Form.Item
              label={<span className="form-label">用户名 / Username</span>}
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input placeholder="例如 admin" autoComplete="username" />
            </Form.Item>
            <Form.Item
              label={<span className="form-label">密码 / Password</span>}
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password placeholder="••••••••" autoComplete="current-password" />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                block
                loading={loading}
                className="login-btn"
              >
                登&nbsp;&nbsp;录&nbsp;&nbsp;&nbsp;<span className="arr">→</span>
              </Button>
            </Form.Item>
          </Form>

          <div className="login-foot">
            <span className="edl-eyebrow">© {dayjs().format('YYYY')} Market Data Collection Center · 内部限阅</span>
            <span className="edl-mono login-foot-build">build · {dayjs().format('YY.MM.DD')}</span>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Login;
