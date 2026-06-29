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

export const DashboardExpressSection: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
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
      {/* 每日速递推送区 */}
      {reportSectionExpanded && (
        <div className="dash-report edl-rise edl-rise-3c" style={{ marginTop: 16 }}>
          <div className="dash-report-bar">
            <div className="dash-report-left">
              <SendOutlined className="dash-report-icon" />
              <div>
                <div className="edl-eyebrow" style={{ marginBottom: 2 }}>每日速递</div>
                <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
                  自动汇总爬虫采集数据，生成速递长图推送到钉钉群
                </span>
              </div>
            </div>
            <Button
              icon={<PlusOutlined />}
              loading={generatingExpress}
              disabled={!canGenerateReports}
              title={!canGenerateReports ? '当前账号无速递生成权限' : undefined}
              onClick={handleGenerateExpress}
              size="small"
            >
              生成今日速递
            </Button>
          </div>
          <div className="dash-report-history">
            <Spin spinning={expressLoading}>
              {expressList.length === 0 && !expressLoading ? (
                <Empty description={'暂无速递，点击「生成今日速递」创建'} style={{ padding: '16px 0' }} />
              ) : (
                <Table<ExpressItem>
                  rowKey="id"
                  size="small"
                  columns={[
                    {
                      title: '标题',
                      dataIndex: 'title',
                      ellipsis: true,
                      render: (text: string) => (
                        <span style={{ fontFamily: 'var(--serif)', fontWeight: 600, fontSize: 13 }}>
                          {text || '—'}
                        </span>
                      ),
                    },
                    {
                      title: '日期',
                      dataIndex: 'express_date',
                      width: 110,
                      render: (date: string) => (
                        <span className="edl-mono" style={{ fontSize: 12 }}>
                          {dayjs(date).format('YYYY·MM·DD')}
                        </span>
                      ),
                    },
                    {
                      title: '板块',
                      dataIndex: 'sections',
                      width: 200,
                      render: (sections: any[]) => (
                        <Space size={4} wrap>
                          {(sections || []).map((s, i) => (
                            <Tag key={i} style={{ fontSize: 11, margin: 0 }}>
                              {s.type} {s.count}
                            </Tag>
                          ))}
                        </Space>
                      ),
                    },
                    {
                      title: '状态',
                      dataIndex: 'push_status',
                      width: 80,
                      render: (status: string) =>
                        status === 'pushed' ? (
                          <Tag color="green" style={{ fontSize: 11 }}>已推送</Tag>
                        ) : (
                          <Tag style={{ fontSize: 11 }}>未推送</Tag>
                        ),
                    },
                    {
                      title: '操作',
                      key: 'action',
                      width: 150,
                      render: (_: unknown, record: ExpressItem) => (
                        <Space size={8}>
                          <a
                            className="dash-rpt-link"
                            onClick={() => handlePreviewExpress(record.id)}
                          >
                            <EyeOutlined /> 预览
                          </a>
                          {record.push_status === 'pushed' ? (
                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
                              <CheckCircleOutlined /> 已推送
                            </span>
                          ) : !canGenerateReports ? (
                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
                              无推送权限
                            </span>
                          ) : (
                            <Popconfirm
                              title="确定推送速递到钉钉群？"
                              description="将截图生成高清长图并 @所有人"
                              onConfirm={() => handlePushExpress(record.id)}
                              okText="推送"
                              cancelText="取消"
                            >
                              <a className="dash-rpt-link" style={{ color: 'var(--vermilion)' }}>
                                <SendOutlined /> {pushingExpressId === record.id ? '推送中' : '推送'}
                              </a>
                            </Popconfirm>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                  dataSource={expressList}
                  pagination={false}
                  locale={{ emptyText: <Empty description="暂无速递" /> }}
                />
              )}
            </Spin>
          </div>
        </div>
      )}

    </>
  );
};
