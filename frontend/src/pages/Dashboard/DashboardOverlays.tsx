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
import { formatFileSize, sanitizeHtmlForPreview, StatCell } from './dashboardShared';
import { DashboardViewContext } from './dashboardViewTypes';

const { RangePicker } = DatePicker;
const { Title } = Typography;

export const DashboardOverlays: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
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
      <StaffDetailDrawer
        staffId={drawerStaffId}
        onClose={() => setDrawerStaffId(null)}
      />

      {/* 备注对话框 */}
      <Modal
        title={noteDialogType === 'daily' ? '生成日报' : '生成周报'}
        open={noteDialogVisible}
        footer={null}
        onCancel={() => setNoteDialogVisible(false)}
      >
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8, fontSize: 13, color: '#666' }}>
            {noteDialogType === 'daily' ? '选择日期：' : '选择周期：'}
          </div>
          {noteDialogType === 'daily' ? (
            <DatePicker
              value={selectedDate}
              onChange={(date) => date && setSelectedDate(date)}
              style={{ width: '100%' }}
            />
          ) : (
            <DatePicker
              picker="week"
              value={selectedDate}
              onChange={(date) => date && setSelectedDate(date)}
              style={{ width: '100%' }}
            />
          )}
        </div>
        <div style={{ marginBottom: 16 }}>
          <Input.TextArea
            placeholder="可选：添加编者备注（将显示在报告中）..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
            rows={3}
            maxLength={500}
            showCount
          />
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
          <Button onClick={() => setNoteDialogVisible(false)}>取消</Button>
          <Button
            onClick={() => handleGenerateConfirm(false)}
            loading={generating !== null}
            disabled={!canGenerateReports}
          >
            仅生成
          </Button>
          <Button
            type="primary"
            onClick={() => handleGenerateConfirm(true)}
            loading={generating !== null}
            disabled={!canGenerateReports}
          >
            生成并推送
          </Button>
        </div>
      </Modal>

      {/* 预览 Modal */}
      <Modal
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={900}
        title={
          previewDetail ? (
            <div className="dash-preview-header">
              <span style={{ fontFamily: 'var(--serif)', fontWeight: 700, flex: 1 }}>
                {previewDetail.title}
              </span>
              <Space size={12}>
                <Button
                  size="small"
                  icon={<PictureOutlined />}
                  onClick={handleConvertToImage}
                >
                  转为图片
                </Button>
                {previewDetail.share_url && (
                  <>
                    <a
                      className="dash-rpt-link"
                      onClick={() => handleCopyLink(previewDetail.share_url!)}
                    >
                      <CopyOutlined /> 复制链接
                    </a>
                    <a
                      className="dash-rpt-link"
                      onClick={() => handleOpenNewWindow(previewDetail.share_url!)}
                    >
                      <ExportOutlined /> 新窗口打开
                    </a>
                  </>
                )}
              </Space>
            </div>
          ) : (
            '报告预览'
          )
        }
        className="dash-preview-modal"
      >
        <Spin spinning={previewLoading}>
          {previewDetail?.html_content ? (
            <iframe
              srcDoc={sanitizeHtmlForPreview(previewDetail.html_content)}
              sandbox=""
              className="dash-preview-iframe"
              title="报告预览"
            />
          ) : (
            !previewLoading && <Empty description="暂无内容" />
          )}
        </Spin>
      </Modal>

      {/* 部门周报预览 */}
      <Modal
        open={departmentWeeklyPreviewVisible}
        onCancel={() => setDepartmentWeeklyPreviewVisible(false)}
        footer={null}
        width={900}
        title={
          departmentWeeklyPreview ? (
            <div className="dash-preview-header">
              <span style={{ fontFamily: 'var(--serif)', fontWeight: 700, flex: 1 }}>
                {departmentWeeklyPreview.title}
              </span>
              <Space size={8} wrap>
                <Tag>{departmentWeeklyPreview.department}</Tag>
                <Tag>
                  {dayjs(departmentWeeklyPreview.week_start).format('MM.DD')} - {dayjs(departmentWeeklyPreview.week_end).format('MM.DD')}
                </Tag>
              </Space>
            </div>
          ) : (
            '部门周报预览'
          )
        }
        className="dash-preview-modal"
      >
        <Spin spinning={departmentWeeklyPreviewLoading}>
          {departmentWeeklyPreview?.html_content ? (
            <iframe
              srcDoc={sanitizeHtmlForPreview(departmentWeeklyPreview.html_content)}
              sandbox=""
              className="dash-preview-iframe"
              title="部门周报预览"
            />
          ) : (
            !departmentWeeklyPreviewLoading && <Empty description="暂无内容" />
          )}
        </Spin>
      </Modal>
    </>
  );
};
