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

export const DashboardOverviewSections: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => {
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
      {/* 头条 */}
      <div className="dash-headline edl-rise edl-rise-1">
        <div>
          <div className="edl-eyebrow">头版 · 日报周报</div>
          <Title className="dash-title" level={1}>
            {filter.mode === 'custom' ? (
              <>阶段<span className="accent">营销</span>进展</>
            ) : filter.mode === 'daily' ? (
              <>{filter.currentDate.format('M月D日')} <span className="accent">营销</span>日报</>
            ) : (
              <>{filter.currentWeekStart.format('M/D')}-{filter.currentWeekStart.add(6, 'day').format('M/D')} <span className="accent">营销</span>周报</>
            )}
          </Title>
          <div className="dash-sub">
            选定区间 · {filter.range[0].format('YYYY/MM/DD')} → {filter.range[1].format('YYYY/MM/DD')}
            <span className="edl-mono"> · {activities.length} 条记录</span>
          </div>
        </div>
        <div className="dash-issue">
          <div className="dash-issue-no">№ {dayjs().format('YYDDD')}</div>
          <div className="edl-eyebrow">本期编号</div>
        </div>
      </div>

      <hr className="edl-rule-strong" />

      <div className="dash-manager edl-rise edl-rise-2">
        <div className="dash-manager-head">
          <div>
            <div className="edl-eyebrow">Management Review</div>
            <h2>管理者复盘视角</h2>
          </div>
          <div className="dash-manager-note">
            <RobotOutlined /> 自动汇总团队动作、商机风险与外部信号变化
          </div>
        </div>
        <Row gutter={[14, 14]}>
          {managementReview.cards.map((card) => (
            <Col xs={12} md={6} key={card.label}>
              <div className="dash-manager-card">
                <div className="dash-manager-icon">{card.icon}</div>
                <div className="dash-manager-value">
                  <span>{card.value}</span>{card.unit}
                </div>
                <div className="dash-manager-label">{card.label}</div>
              </div>
            </Col>
          ))}
        </Row>
        <div className="dash-manager-actions">
          {managementReview.actions.map((item, index) => (
            <div className="dash-manager-action" key={item.title}>
              <span className="edl-mono">0{index + 1}</span>
              <strong>{item.title}</strong>
              <p>{item.text}</p>
            </div>
          ))}
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="dash-filters edl-rise edl-rise-2">
        <Space size={12} wrap>
          {/* 模式切换 */}
          <Segmented
            value={filter.mode}
            onChange={(v) => switchMode(v as 'daily' | 'weekly' | 'custom')}
            options={[
              { label: '日报', value: 'daily' },
              { label: '周报', value: 'weekly' },
              { label: '自定义', value: 'custom' },
            ]}
          />

          {/* 日报模式：日历选择器 */}
          {filter.mode === 'daily' && (
            <Space>
              <Button icon={<LeftOutlined />} onClick={() => goDay(-1)} type="text" size="small" />
              <DatePicker
                value={filter.currentDate}
                onChange={(v) => {
                  if (v) setFilter((f) => ({ ...f, currentDate: v, range: [v.startOf('day'), v.endOf('day')] }));
                }}
                allowClear={false}
                size="small"
                style={{ width: 150, textAlign: 'center' }}
              />
              <Button icon={<RightOutlined />} onClick={() => goDay(1)} type="text" size="small"
                disabled={filter.currentDate.isSame(dayjs(), 'day')} />
              <Button size="small" onClick={() => setFilter((f) => ({ ...f, currentDate: dayjs(), range: [dayjs().startOf('day'), dayjs().endOf('day')] }))}>
                今天
              </Button>
            </Space>
          )}

          {/* 周报模式：日历选择器 */}
          {filter.mode === 'weekly' && (
            <Space>
              <Button icon={<LeftOutlined />} onClick={() => goWeek(-1)} type="text" size="small" />
              <DatePicker
                picker="week"
                value={filter.currentWeekStart}
                onChange={(v) => {
                  if (v) setFilter((f) => ({ ...f, currentWeekStart: v, range: [v, v.add(6, 'day').endOf('day')] }));
                }}
                allowClear={false}
                size="small"
                style={{ width: 200, textAlign: 'center' }}
              />
              <Button icon={<RightOutlined />} onClick={() => goWeek(1)} type="text" size="small"
                disabled={filter.currentWeekStart.isSame(dayjs().startOf('week'))} />
              <Button size="small" onClick={() => setFilter((f) => ({ ...f, currentWeekStart: dayjs().startOf('week'), range: [dayjs().startOf('week'), dayjs().startOf('week').add(6, 'day').endOf('day')] }))}>
                本周
              </Button>
            </Space>
          )}

          {/* 自定义模式：RangePicker */}
          {filter.mode === 'custom' && (
            <RangePicker
              value={filter.customRange}
              onChange={(v) =>
                v && v[0] && v[1] && setFilter((f) => ({ ...f, customRange: [v[0]!, v[1]!], range: [v[0]!, v[1]!] }))
              }
              allowClear={false}
            />
          )}

          {/* 快速跳转按钮 */}
          <Button size="small" onClick={() => {
            setFilter((f) => ({
              ...f,
              mode: 'custom',
              customRange: [dayjs('2026-06-03'), dayjs('2026-06-13')],
              range: [dayjs('2026-06-03'), dayjs('2026-06-13')],
            }));
          }}>
            近期数据 (6/3-6/13)
          </Button>
          <Select
            placeholder="人员"
            allowClear
            style={{ width: 160 }}
            value={filter.userId}
            onChange={(v) => setFilter((f) => ({ ...f, userId: v }))}
            options={staffList.map((s) => ({ label: s.name, value: s.id }))}
            showSearch
            optionFilterProp="label"
          />
          <Select
            placeholder="岗位类型"
            allowClear
            style={{ width: 160 }}
            value={filter.role}
            onChange={(v) => setFilter((f) => ({ ...f, role: v }))}
            options={roles.map((r) => ({ label: r, value: r }))}
          />
          <Select
            placeholder="组织 / 部门"
            allowClear
            style={{ width: 180 }}
            value={filter.department}
            onChange={(v) => setFilter((f) => ({ ...f, department: v }))}
            options={departments.map((d) => ({ label: d, value: d }))}
          />
          <Select
            mode="multiple"
            placeholder="行为类型"
            allowClear
            style={{ minWidth: 240 }}
            value={filter.actionTypes}
            onChange={(v) => setFilter((f) => ({ ...f, actionTypes: v }))}
            options={ACTION_TYPES.map((t) => ({ label: t.label, value: t.value }))}
            maxTagCount={2}
          />
          <Input
            allowClear
            placeholder="搜索 客户 / 摘要 / 人员"
            prefix={<SearchOutlined />}
            style={{ width: 240 }}
            value={filter.keyword}
            onChange={(e) => setFilter((f) => ({ ...f, keyword: e.target.value }))}
          />
          <a className="dash-reload" onClick={loadActivities}>
            <ReloadOutlined /> 刷新
          </a>
        </Space>
      </div>

      {/* 统计卡片：左侧四枚 + 右侧行为分布 */}
      <Row gutter={[20, 20]} className="dash-stats edl-rise edl-rise-3">
        <Col xs={24} md={14}>
          <Row gutter={[20, 20]}>
            <Col xs={12} md={6}>
              <StatCell label="今日活动" value={todayActivities} unit="条" />
            </Col>
            <Col xs={12} md={6}>
              <StatCell label="本周活动" value={weekActivities} unit="条" highlight />
            </Col>
            <Col xs={12} md={6}>
              <StatCell label="活跃人数" value={activeUsers} unit="人" />
            </Col>
            <Col xs={12} md={6}>
              <StatCell label="跟进商机" value={followingOpps} unit="个" />
            </Col>
          </Row>
        </Col>
        <Col xs={24} md={10}>
          <div className="dash-distribution edl-card">
            <div className="dash-distribution-head">
              <div className="edl-eyebrow">本期 · 行为占比</div>
              <div className="dash-distribution-total">
                <span className="edl-display">{activities.length}</span>
                <span className="edl-eyebrow">total</span>
              </div>
            </div>
            <div className="dash-distribution-list">
              {actionDistribution.length === 0 && (
                <div style={{ padding: 24, color: 'var(--ink-faint)' }}>暂无数据</div>
              )}
              {actionDistribution.map((d) => (
                <div className="dist-row" key={d.value}>
                  <span className="dist-label" style={{ color: d.ink }}>
                    {d.label}
                  </span>
                  <div className="dist-bar-wrap">
                    <div
                      className="dist-bar"
                      style={{ width: `${d.pct}%`, background: d.ink }}
                    />
                  </div>
                  <span className="dist-count edl-mono">{d.count}</span>
                </div>
              ))}
            </div>
          </div>
        </Col>
      </Row>

    </>
  );
};
