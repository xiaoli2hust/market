import React from 'react';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
} from 'antd';
import {
  AlertOutlined,
  BarChartOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  CopyOutlined,
  DeleteOutlined,
  ExportOutlined,
  EyeOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  LeftOutlined,
  PictureOutlined,
  PlusOutlined,
  ReloadOutlined,
  RightOutlined,
  RobotOutlined,
  SearchOutlined,
  SendOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { ProTable } from '@ant-design/pro-components';
import dayjs from 'dayjs';
import {
  ActivityItem,
  DepartmentWeeklyReportItem,
  ExpressItem,
  ReportItem,
} from '@/services/api';
import { ACTION_TYPES, getActionMeta } from '@/constants/actionTypes';
import StaffDetailDrawer from '@/components/StaffDetailDrawer';
import { formatFileSize, getWeekMonday, sanitizeHtmlForPreview, StatCell } from './dashboardShared';
import { DashboardViewContext } from './dashboardViewTypes';

const { RangePicker } = DatePicker;
const { Title } = Typography;

export const DashboardReportSection: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
  const {
    filter,
    activities,
    managementReview,
    switchMode,
    goDay,
    goWeek,
    setFilter,
    staffList,
    roles,
    departments,
    loadActivities,
    todayActivities,
    weekActivities,
    activeUsers,
    followingOpps,
    actionDistribution,
    reportTotal,
    generating,
    canGenerateReports,
    handleGenerateClick,
    canViewReports,
    reportSectionExpanded,
    setReportSectionExpanded,
    reportTab,
    setReportTab,
    reportLoading,
    reports,
    handlePreview,
    handleCopyLink,
    handleOpenNewWindow,
    handlePushReport,
    pushingReportId,
    departmentWeeklyTotal,
    departmentWeeklyWeek,
    setDepartmentWeeklyWeek,
    departmentWeeklyDepartment,
    setDepartmentWeeklyDepartment,
    departmentWeeklyTitle,
    setDepartmentWeeklyTitle,
    loadDepartmentWeeklyReports,
    handleUploadDepartmentWeekly,
    departmentWeeklyUploading,
    departmentWeeklyLoading,
    departmentWeeklyReports,
    handlePreviewDepartmentWeekly,
    handleDeleteDepartmentWeekly,
    generatingExpress,
    handleGenerateExpress,
    expressLoading,
    expressList,
    handlePreviewExpress,
    pushingExpressId,
    handlePushExpress,
    biddingExpress,
    biddingPeriod,
    setBiddingPeriod,
    generatingBidding,
    canManageExpress,
    handleGenerateBidding,
    pushingBidding,
    handlePushBidding,
    handlePreviewBidding,
    tab,
    setTab,
    loading,
    columns,
    groupedByStaff,
    setDrawerStaffId,
    groupedByOpp,
    drawerStaffId,
    noteDialogType,
    noteDialogVisible,
    setNoteDialogVisible,
    selectedDate,
    setSelectedDate,
    noteText,
    setNoteText,
    handleGenerateConfirm,
    previewVisible,
    setPreviewVisible,
    previewDetail,
    handleConvertToImage,
    previewLoading,
    departmentWeeklyPreviewVisible,
    setDepartmentWeeklyPreviewVisible,
    departmentWeeklyPreview,
    departmentWeeklyPreviewLoading,
  } = ctx;

  return (
    <>
      {/* 报告生成区 */}
      <div className="dash-report edl-rise edl-rise-3b">
        <div className="dash-report-bar">
          <div className="dash-report-left">
            <FileTextOutlined className="dash-report-icon" />
            <div>
              <div className="edl-eyebrow" style={{ marginBottom: 2 }}>报告中心</div>
              <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
                基于当前数据生成日报 / 周报页面，推送给领导查阅
                {reportTotal > 0 && <span className="edl-mono"> · 已生成 {reportTotal} 份</span>}
              </span>
            </div>
          </div>
          <Space size={8}>
            <Button
              icon={<PlusOutlined />}
              loading={generating === 'daily'}
              disabled={!canGenerateReports}
              title={!canGenerateReports ? '当前账号无报告生成权限' : undefined}
              onClick={() => handleGenerateClick('daily')}
              size="small"
            >
              生成日报
            </Button>
            <Button
              icon={<PlusOutlined />}
              loading={generating === 'weekly'}
              disabled={!canGenerateReports}
              title={!canGenerateReports ? '当前账号无报告生成权限' : undefined}
              onClick={() => handleGenerateClick('weekly')}
              size="small"
            >
              生成周报
            </Button>
            {canViewReports && (
              <a
                className="dash-report-toggle"
                onClick={() => setReportSectionExpanded(!reportSectionExpanded)}
              >
                {reportSectionExpanded ? '收起历史 ▲' : '历史报告 ▼'}
              </a>
            )}
          </Space>
        </div>

        {reportSectionExpanded && (
          <div className="dash-report-history">
            <Tabs
              activeKey={reportTab}
              onChange={(k) => setReportTab(k as 'all' | 'daily' | 'weekly')}
              size="small"
              items={[
                { key: 'all', label: '全部' },
                { key: 'daily', label: '日报' },
                { key: 'weekly', label: '周报' },
              ]}
            />
            <Spin spinning={reportLoading}>
              {reports.length === 0 && !reportLoading ? (
                <Empty description="暂无报告" style={{ padding: '16px 0' }} />
              ) : (
                <Table<ReportItem>
                  rowKey="id"
                  size="small"
                  columns={[
                    {
                      title: '标题',
                      dataIndex: 'title',
                      ellipsis: true,
	                      render: (text: string, record: ReportItem) => (
	                        <Space size={6}>
	                          <span style={{ fontFamily: 'var(--serif)', fontWeight: 600, fontSize: 13 }}>
	                            {text || '—'}
	                          </span>
	                          <Tag style={{ margin: 0, fontSize: 11 }}>v{record.version || 1}</Tag>
	                        </Space>
	                      ),
	                    },
                    {
                      title: '类型',
                      dataIndex: 'report_type',
                      width: 70,
                      render: (type: string) => (
                        <Tag color={type === 'daily' ? 'blue' : 'orange'} style={{ margin: 0, fontSize: 11 }}>
                          {type === 'daily' ? '日报' : '周报'}
                        </Tag>
                      ),
                    },
	                    {
	                      title: '日期',
                      dataIndex: 'report_date',
                      width: 110,
                      render: (date: string) => (
                        <span className="edl-mono" style={{ fontSize: 12 }}>
                          {dayjs(date).format('YYYY·MM·DD')}
                        </span>
	                      ),
	                    },
	                    {
	                      title: '状态',
	                      dataIndex: 'status',
	                      width: 86,
	                      render: (status: string) => {
	                        const meta = status === 'published'
	                          ? { color: 'green', text: '已发布' }
	                          : status === 'superseded'
	                            ? { color: 'default', text: '已归档' }
	                            : { color: 'blue', text: '草稿' };
	                        return <Tag color={meta.color} style={{ margin: 0, fontSize: 11 }}>{meta.text}</Tag>;
	                      },
	                    },
	                    {
	                      title: '操作',
	                      key: 'action',
                      width: 260,
                      render: (_: unknown, record: ReportItem) => (
                        <Space size={8}>
                          <a className="dash-rpt-link" onClick={() => handlePreview(record)}>
                            <EyeOutlined /> 预览
                          </a>
                          {record.share_url && (
                            <>
                              <a className="dash-rpt-link" onClick={() => handleCopyLink(record.share_url)}>
                                <CopyOutlined /> 复制
                              </a>
                              <a className="dash-rpt-link" onClick={() => handleOpenNewWindow(record.share_url)}>
                                <ExportOutlined /> 新窗口
                              </a>
                            </>
                          )}
	                          {record.status === 'published' ? (
	                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
	                              <CheckCircleOutlined /> 已发布
	                            </span>
	                          ) : record.status === 'superseded' ? (
	                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
	                              已归档
	                            </span>
	                          ) : !canGenerateReports ? (
                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
                              无推送权限
                            </span>
	                          ) : (
                            <Popconfirm
                              title="确定推送到钉钉群？"
                              description="推送后将发送 Markdown 消息给群成员"
                              onConfirm={() => handlePushReport(record.id)}
                              okText="推送"
                              cancelText="取消"
                            >
                              <a className="dash-rpt-link" style={{ color: 'var(--vermilion)' }}>
                                <SendOutlined /> {pushingReportId === record.id ? '推送中' : '推送'}
                              </a>
                            </Popconfirm>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                  dataSource={reports}
                  pagination={false}
                  locale={{ emptyText: <Empty description="暂无报告" /> }}
                />
              )}
            </Spin>
          </div>
        )}
      </div>

    </>
  );
};
