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

export const DashboardActivitySection: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
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
      {/* 列表区 */}
      <div className="dash-feed edl-rise edl-rise-4">
        <div className="dash-feed-head">
          <div>
            <div className="edl-eyebrow">第二版 · 字段动作记录</div>
            <h2 className="dash-feed-title">营销动作流水</h2>
          </div>
          <Tabs
            activeKey={tab}
            onChange={(k) => setTab(k as any)}
            items={[
              { key: 'time', label: '按时间线' },
              { key: 'staff', label: '按人员' },
              { key: 'opportunity', label: '按商机' },
            ]}
          />
        </div>

        <Spin spinning={loading}>
          {tab === 'time' && (
            <ProTable<ActivityItem>
              search={false}
              options={false}
              rowKey="id"
              columns={columns}
              dataSource={activities}
              className="edl-table"
              scroll={{ x: 660 }}
              pagination={{ pageSize: 20, showSizeChanger: false }}
              locale={{ emptyText: <Empty description="本期暂无营销动作" /> }}
            />
          )}

          {tab === 'staff' &&
            (groupedByStaff.length === 0 ? (
              <Empty description="本期暂无营销动作" />
            ) : (
              <div className="dash-groups">
                {groupedByStaff.map(([name, items]) => (
                  <Card key={name} className="dash-group" bordered={false}>
                    <div className="dash-group-head">
                      <div>
                        <span className="edl-name-stamp" onClick={() => {
                          const u = staffList.find((s) => s.name === name);
                          if (u) setDrawerStaffId(u.id);
                        }}>{name}</span>
                        <span className="edl-mono dash-group-meta">
                          · {items[0]?.user_department || '—'} · {items.length} 条
                        </span>
                      </div>
                      <span className="edl-display dash-group-num">
                        {String(items.length).padStart(2, '0')}
                      </span>
                    </div>
                    <ul className="dash-group-list">
                      {items.map((it) => (
                        <li key={it.id}>
                          <span
                            className="edl-action-chip"
                            style={{ color: getActionMeta(it.action_type).ink }}
                          >
                            {getActionMeta(it.action_type).label}
                          </span>
                          <span className="dash-group-summary">{it.summary || it.description?.substring(0, 80) || '—'}</span>
                          <span className="edl-mono dash-group-date">
                            {dayjs(it.activity_date).format('MM·DD')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                ))}
              </div>
            ))}

          {tab === 'opportunity' &&
            (groupedByOpp.length === 0 ? (
              <Empty description="本期暂无营销动作" />
            ) : (
              <div className="dash-groups">
                {groupedByOpp.map(([name, items]) => (
                  <Card key={name} className="dash-group" bordered={false}>
                    <div className="dash-group-head">
                      <div>
                        <span className="edl-serif" style={{ fontWeight: 700 }}>{name}</span>
                        <span className="edl-mono dash-group-meta"> · {items.length} 条</span>
                      </div>
                      <span className="edl-display dash-group-num">
                        {String(items.length).padStart(2, '0')}
                      </span>
                    </div>
                    <ul className="dash-group-list">
                      {items.slice(0, 8).map((it) => (
                        <li key={it.id}>
                          <span
                            className="edl-action-chip"
                            style={{ color: getActionMeta(it.action_type).ink }}
                          >
                            {getActionMeta(it.action_type).label}
                          </span>
                          <span className="dash-group-summary">
                            <strong>{it.user_name}</strong> · {it.summary || '—'}
                          </span>
                          <span className="edl-mono dash-group-date">
                            {dayjs(it.activity_date).format('MM·DD')}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                ))}
              </div>
            ))}
        </Spin>
      </div>

    </>
  );
};
