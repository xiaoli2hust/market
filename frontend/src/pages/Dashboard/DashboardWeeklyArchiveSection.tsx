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

export const DashboardWeeklyArchiveSection: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
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
      {/* 部门周报归档 */}
      {reportSectionExpanded && (
        <div className="dash-report dash-weekly-archive edl-rise edl-rise-3c" style={{ marginTop: 16 }}>
          <div className="dash-report-bar">
            <div className="dash-report-left">
              <CalendarOutlined className="dash-report-icon" />
              <div>
                <div className="edl-eyebrow" style={{ marginBottom: 2 }}>部门周报归档</div>
                <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
                  保存部门向公司提交的 HTML 周报，按周回看部门重点工作
                  {departmentWeeklyTotal > 0 && <span className="edl-mono"> · 当前筛选 {departmentWeeklyTotal} 份</span>}
                </span>
              </div>
            </div>
          </div>

          <div className="dash-report-history">
            <div className="dash-weekly-form">
              <DatePicker
                picker="week"
                value={departmentWeeklyWeek}
                onChange={(date) => date && setDepartmentWeeklyWeek(getWeekMonday(date))}
                allowClear={false}
              />
              <Input
                value={departmentWeeklyDepartment}
                onChange={(e) => setDepartmentWeeklyDepartment(e.target.value)}
                onPressEnter={loadDepartmentWeeklyReports}
                placeholder="部门名称，如：市场部"
                maxLength={100}
              />
              <Input
                value={departmentWeeklyTitle}
                onChange={(e) => setDepartmentWeeklyTitle(e.target.value)}
                placeholder="周报标题，可不填"
                maxLength={200}
              />
              <Button icon={<ReloadOutlined />} onClick={loadDepartmentWeeklyReports}>
                查看
              </Button>
              <Upload
                accept=".html,.htm,text/html"
                showUploadList={false}
                beforeUpload={(file) => {
                  void handleUploadDepartmentWeekly(file as File);
                  return Upload.LIST_IGNORE;
                }}
              >
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  loading={departmentWeeklyUploading}
                  disabled={!canGenerateReports || departmentWeeklyUploading}
                  title={!canGenerateReports ? '当前账号无周报归档权限' : undefined}
                >
                  上传HTML
                </Button>
              </Upload>
            </div>

            <Spin spinning={departmentWeeklyLoading}>
              {departmentWeeklyReports.length === 0 && !departmentWeeklyLoading ? (
                <Empty description="当前周暂无部门周报归档" style={{ padding: '16px 0' }} />
              ) : (
                <Table<DepartmentWeeklyReportItem>
                  rowKey="id"
                  size="small"
                  scroll={{ x: 760 }}
                  columns={[
                    {
                      title: '周报',
                      dataIndex: 'title',
                      ellipsis: true,
                      render: (text: string, record: DepartmentWeeklyReportItem) => (
                        <div className="dash-weekly-title">
                          <strong>{text || record.file_name}</strong>
                          <span>{record.file_name}</span>
                        </div>
                      ),
                    },
                    {
                      title: '周期',
                      dataIndex: 'week_start',
                      width: 170,
                      render: (_: string, record: DepartmentWeeklyReportItem) => (
                        <span className="edl-mono" style={{ fontSize: 12 }}>
                          {dayjs(record.week_start).format('MM.DD')} - {dayjs(record.week_end).format('MM.DD')}
                        </span>
                      ),
                    },
                    {
                      title: '部门',
                      dataIndex: 'department',
                      width: 120,
                      render: (text: string) => <Tag style={{ margin: 0 }}>{text}</Tag>,
                    },
                    {
                      title: '大小',
                      dataIndex: 'content_length',
                      width: 88,
                      render: (value: number) => <span className="edl-mono">{formatFileSize(value)}</span>,
                    },
                    {
                      title: '归档人',
                      dataIndex: 'uploaded_by',
                      width: 110,
                      render: (text: string) => text || '—',
                    },
                    {
                      title: '操作',
                      key: 'action',
                      width: 150,
                      render: (_: unknown, record: DepartmentWeeklyReportItem) => (
                        <Space size={10}>
                          <a className="dash-rpt-link" onClick={() => handlePreviewDepartmentWeekly(record.id)}>
                            <EyeOutlined /> 预览
                          </a>
                          {canGenerateReports ? (
                            <Popconfirm
                              title="删除这份部门周报？"
                              description="删除后不会出现在归档列表中"
                              onConfirm={() => handleDeleteDepartmentWeekly(record.id)}
                              okText="删除"
                              cancelText="取消"
                            >
                              <a className="dash-rpt-link" style={{ color: 'var(--vermilion)' }}>
                                <DeleteOutlined /> 删除
                              </a>
                            </Popconfirm>
                          ) : (
                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>无删除权限</span>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                  dataSource={departmentWeeklyReports}
                  pagination={false}
                  locale={{ emptyText: <Empty description="当前周暂无部门周报归档" /> }}
                />
              )}
            </Spin>
          </div>
        </div>
      )}

    </>
  );
};
