import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Empty,
  message,
  Modal,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import { FileTextOutlined, CopyOutlined, EyeOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchReports,
  fetchReportDetail,
  generateReport,
  ReportItem,
  ReportDetail,
} from '@/services/api';
import './reports.less';

const { Title } = Typography;

const Reports: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState<'daily' | 'weekly' | null>(null);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [tab, setTab] = useState<'all' | 'daily' | 'weekly'>('all');

  // 预览
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewDetail, setPreviewDetail] = useState<ReportDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  /* —— 加载列表 —— */
  const loadReports = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (tab !== 'all') params.report_type = tab;
      const resp = await fetchReports(params);
      setReports(resp?.items || []);
      setTotal(resp?.total || 0);
    } catch {
      message.error('加载报告列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, tab]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  /* —— 生成报告 —— */
  const handleGenerate = async (type: 'daily' | 'weekly') => {
    setGenerating(type);
    try {
      const date =
        type === 'daily'
          ? dayjs().format('YYYY-MM-DD')
          : dayjs().startOf('week').format('YYYY-MM-DD');
      await generateReport({ report_type: type, date });
      message.success(type === 'daily' ? '日报生成成功' : '周报生成成功');
      loadReports();
    } catch {
      message.error('生成报告失败，请稍后重试');
    } finally {
      setGenerating(null);
    }
  };

  /* —— 预览 —— */
  const handlePreview = async (record: ReportItem) => {
    setPreviewVisible(true);
    setPreviewDetail(null);
    setPreviewLoading(true);
    try {
      const detail = await fetchReportDetail(record.id);
      setPreviewDetail(detail);
    } catch {
      message.error('加载报告详情失败');
    } finally {
      setPreviewLoading(false);
    }
  };

  /* —— 复制分享链接 —— */
  const handleCopyLink = (shareUrl: string) => {
    const fullUrl = window.location.origin + shareUrl;
    navigator.clipboard.writeText(fullUrl).then(
      () => message.success('链接已复制'),
      () => message.error('复制失败，请手动复制'),
    );
  };

  /* —— 列定义 —— */
  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      ellipsis: true,
      render: (text: string) => (
        <span style={{ fontFamily: 'var(--serif)', fontWeight: 700 }}>{text || '—'}</span>
      ),
    },
    {
      title: '类型',
      dataIndex: 'report_type',
      width: 100,
      render: (type: string) => (
        <Tag color={type === 'daily' ? 'blue' : 'orange'} style={{ margin: 0 }}>
          {type === 'daily' ? '日报' : '周报'}
        </Tag>
      ),
    },
    {
      title: '日期',
      dataIndex: 'report_date',
      width: 130,
      render: (date: string) => (
        <span className="edl-mono">{dayjs(date).format('YYYY·MM·DD')}</span>
      ),
    },
    {
      title: '推送状态',
      dataIndex: 'push_status',
      width: 100,
      render: (status: string) => {
        if (status === 'sent') return <Tag color="green">已推送</Tag>;
        if (status === 'failed') return <Tag color="red">推送失败</Tag>;
        return <Tag>未推送</Tag>;
      },
    },
    {
      title: '生成时间',
      dataIndex: 'created_at',
      width: 170,
      render: (date: string) => (
        <span className="edl-mono">{dayjs(date).format('YYYY·MM·DD HH:mm')}</span>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: unknown, record: ReportItem) => (
        <Space size={4}>
          <a className="rpt-action-link" onClick={() => handlePreview(record)}>
            <EyeOutlined /> 预览
          </a>
          <a className="rpt-action-link" onClick={() => handleCopyLink(record.share_url)}>
            <CopyOutlined /> 复制链接
          </a>
        </Space>
      ),
    },
  ];

  return (
    <div className="rpt">
      {/* 头条 */}
      <div className="rpt-headline edl-rise edl-rise-1">
        <div>
          <div className="edl-eyebrow">特刊 · 报告中心</div>
          <Title className="rpt-title" level={1}>
            报告<span className="accent">管理</span>
          </Title>
          <div className="rpt-sub">
            生成与分发营销日报 / 周报
            <span className="edl-mono"> · 共 {total} 份报告</span>
          </div>
        </div>
      </div>

      <hr className="edl-rule-strong" />

      {/* 操作区 */}
      <div className="rpt-actions edl-rise edl-rise-2">
        <Space size={12}>
          <Button
            type="primary"
            danger
            icon={<FileTextOutlined />}
            loading={generating === 'daily'}
            onClick={() => handleGenerate('daily')}
          >
            生成今日日报
          </Button>
          <Button
            type="primary"
            danger
            icon={<FileTextOutlined />}
            loading={generating === 'weekly'}
            onClick={() => handleGenerate('weekly')}
          >
            生成本周周报
          </Button>
        </Space>
      </div>

      {/* 列表区 */}
      <div className="rpt-feed edl-rise edl-rise-3">
        <div className="rpt-feed-head">
          <div>
            <div className="edl-eyebrow">归档 · 报告列表</div>
            <h2 className="rpt-feed-title">已生成报告</h2>
          </div>
          <Tabs
            activeKey={tab}
            onChange={(k) => {
              setTab(k as 'all' | 'daily' | 'weekly');
              setPage(1);
            }}
            items={[
              { key: 'all', label: '全部' },
              { key: 'daily', label: '日报' },
              { key: 'weekly', label: '周报' },
            ]}
          />
        </div>

        <Spin spinning={loading}>
          <Table<ReportItem>
            rowKey="id"
            columns={columns}
            dataSource={reports}
            className="edl-table"
            pagination={{
              current: page,
              pageSize,
              total,
              showSizeChanger: false,
              onChange: (p) => setPage(p),
            }}
            locale={{ emptyText: <Empty description="暂无报告" /> }}
          />
        </Spin>
      </div>

      {/* 预览 Modal */}
      <Modal
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={860}
        title={
          previewDetail ? (
            <div className="rpt-preview-header">
              <span style={{ fontFamily: 'var(--serif)', fontWeight: 700 }}>
                {previewDetail.title}
              </span>
              {previewDetail.share_url && (
                <a
                  className="rpt-share-link edl-mono"
                  onClick={() => handleCopyLink(previewDetail.share_url)}
                >
                  <CopyOutlined /> 复制分享链接
                </a>
              )}
            </div>
          ) : (
            '报告预览'
          )
        }
        className="rpt-preview-modal"
      >
        <Spin spinning={previewLoading}>
          {previewDetail?.html_content ? (
            <div
              className="rpt-preview-content"
              dangerouslySetInnerHTML={{ __html: previewDetail.html_content }}
            />
          ) : (
            !previewLoading && <Empty description="暂无内容" />
          )}
        </Spin>
      </Modal>
    </div>
  );
};

export default Reports;
