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

export const DashboardBiddingExpressSection: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
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
      {/* 标讯速递 */}
      {reportSectionExpanded && (
        <div className="dash-report edl-rise edl-rise-3d" style={{ marginTop: 16 }}>
          <div className="dash-report-bar">
            <div className="dash-report-left">
              <FileSearchOutlined className="dash-report-icon" />
              <div>
                <div className="edl-eyebrow" style={{ marginBottom: 2 }}>标讯速递</div>
                <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
                  结构化标讯数据整合，按类型分组 + 高金额/重点匹配置顶
                  {biddingExpress?.period_label && <span className="edl-mono"> · {biddingExpress.period_label}</span>}
                  {biddingExpress?.total != null && <span className="edl-mono"> · 命中 {biddingExpress.total} 条</span>}
                </span>
              </div>
            </div>
            <Space size={8}>
              <Segmented
                size="small"
                value={biddingPeriod}
                onChange={(value) => setBiddingPeriod(value as 'day' | 'week' | 'month' | 'all')}
                options={[
                  { label: '今日', value: 'day' },
                  { label: '本周', value: 'week' },
                  { label: '本月', value: 'month' },
                  { label: '全部', value: 'all' },
                ]}
              />
              <Button
                icon={<ReloadOutlined />}
                loading={generatingBidding}
                disabled={!canManageExpress}
                title={!canManageExpress ? '当前账号无标讯速递生成权限' : undefined}
                onClick={handleGenerateBidding}
                size="small"
              >
                生成标讯速递
              </Button>
              {biddingExpress?.status === 'ok' && canManageExpress && (
                <Popconfirm
                  title="确定推送标讯速递到钉钉群？"
                  description={`将推送 ${biddingExpress.total} 条标讯，按类型分组展示`}
                  onConfirm={handlePushBidding}
                  okText="推送"
                  cancelText="取消"
                >
                  <Button icon={<SendOutlined />} loading={pushingBidding} size="small" style={{ color: 'var(--vermilion)', borderColor: 'var(--vermilion)' }}>
                    推送钉钉
                  </Button>
                </Popconfirm>
              )}
              {biddingExpress?.status === 'ok' && (
                <Button size="small" onClick={handlePreviewBidding}>
                  预览
                </Button>
              )}
            </Space>
          </div>
          {biddingExpress?.status === 'ok' && biddingExpress.groups && (
            <div style={{ padding: '8px 16px', fontSize: 12, color: 'var(--ink-faint)' }}>
              {biddingExpress.groups.map((g: any) => (
                <Tag key={g.subtype} style={{ fontSize: 11 }}>{g.label} {g.count}</Tag>
              ))}
              {biddingExpress.high_value_count ? <Tag color="orange" style={{ fontSize: 11 }}>💰 高金额 {biddingExpress.high_value_count}</Tag> : null}
              {biddingExpress.priority_count ? <Tag color="red" style={{ fontSize: 11 }}>🎯 重点匹配 {biddingExpress.priority_count}</Tag> : null}
              {biddingExpress.source_total != null ? <Tag style={{ fontSize: 11 }}>来源返回 {biddingExpress.source_total}</Tag> : null}
            </div>
          )}
          {biddingExpress?.status === 'empty' && (
            <div style={{ padding: '12px 16px', fontSize: 13, color: 'var(--ink-faint)' }}>
              当前周期暂无命中标讯，可切换到本月或全部查看历史数据
            </div>
          )}
        </div>
      )}

    </>
  );
};
