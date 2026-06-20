import React, { useState } from 'react';
import { history } from '@umijs/max';
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
      setAuth(result.token, result.user);
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
      {/* 左：刊头大字 */}
      <aside className="login-left">
        <div className="login-eyebrow edl-eyebrow">采集 · 洞察 · 驱动</div>
        <div className="login-stamp">№ {dayjs().format('YYYYMMDD')}</div>

        <h1 className="login-title">
          <span className="zh">营销数据</span>
          <span className="zh">驾驶舱</span>
          <span className="en">Marketing Data Cockpit</span>
        </h1>

        <div className="login-quote">
          <blockquote>
            "情报，是先于结果的事实。"
          </blockquote>
          <cite>— 编辑部按</cite>
        </div>

        <div className="login-features">
          <div className="login-feature">
            <span className="feat-num">01</span>
            <div>
              <div className="feat-zh">每日营销动作快讯</div>
              <div className="feat-en edl-eyebrow">Daily field briefing</div>
            </div>
          </div>
          <div className="login-feature">
            <span className="feat-num">02</span>
            <div>
              <div className="feat-zh">商机管线一图速览</div>
              <div className="feat-en edl-eyebrow">Opportunity pipeline</div>
            </div>
          </div>
          <div className="login-feature">
            <span className="feat-num">03</span>
            <div>
              <div className="feat-zh">团队画像与活跃度</div>
              <div className="feat-en edl-eyebrow">Team activity portrait</div>
            </div>
          </div>
        </div>

        <div className="login-decor-cn">採集 · 洞察 · 驅動</div>
      </aside>

      {/* 右：登录表单 */}
      <section className="login-right">
        <div className="login-form-wrap">
          <div className="edl-eyebrow">Sign In · 凭证登录</div>
          <h2 className="login-form-title">
            进入<span className="seal">编辑部</span>
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
            <span className="edl-eyebrow">© {dayjs().format('YYYY')} 编辑部 · 内部限阅</span>
            <span className="edl-mono login-foot-build">build · {dayjs().format('YY.MM.DD')}</span>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Login;
