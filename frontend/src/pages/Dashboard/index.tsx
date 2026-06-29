import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Tag } from 'antd';
import { AlertOutlined, BarChartOutlined, CheckCircleOutlined, FileSearchOutlined } from '@ant-design/icons';
import { ProColumns } from '@ant-design/pro-components';
import dayjs, { Dayjs } from 'dayjs';
import {
  ActivityItem,
  fetchActivities,
  fetchDepartments,
  fetchStaff,
  Staff,
  fetchReports,
  fetchDepartmentWeeklyReports,
  fetchDepartmentWeeklyReportDetail,
  fetchExpressList,
  getLatestBiddingExpress,
  fetchIntelligenceStats,
  getApiErrorMessage,
  getCurrentUser,
  ReportItem,
  ReportDetail,
  DepartmentWeeklyReportItem,
  DepartmentWeeklyReportDetail,
  ExpressItem,
  userHasPermission,
} from '@/services/api';
import { ACTION_TYPES, getActionMeta } from '@/constants/actionTypes';
import { FilterState, getWeekMonday, sanitizeHtmlForPreview } from './dashboardShared';
import { DashboardView } from './DashboardView';
import { useDashboardReportActions } from './useDashboardReportActions';
import './dashboard.less';

const Dashboard: React.FC = () => {
  const currentUser = getCurrentUser();
  const canViewReports = userHasPermission(currentUser, 'reports:view');
  const canGenerateReports = userHasPermission(currentUser, 'reports:generate');
  const canManageExpress = userHasPermission(currentUser, 'management:express');
  const [filter, setFilter] = useState<FilterState>(() => {
    const today = dayjs();
    // 如果有数据，默认显示最近有数据的日期范围
    return {
      mode: 'custom',
      currentDate: today,
      currentWeekStart: today.startOf('week'),
      customRange: [today.subtract(10, 'day'), today],
      range: [today.subtract(10, 'day'), today],
      actionTypes: [],
      keyword: '',
    };
  });

  const [staffList, setStaffList] = useState<Staff[]>([]);
  const [departments, setDepartments] = useState<string[]>([]);
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<'time' | 'staff' | 'opportunity'>('time');

  const [drawerStaffId, setDrawerStaffId] = useState<number | null>(null);

  // —— 报告相关状态 ——
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [reportTotal, setReportTotal] = useState(0);
  const [reportTab, setReportTab] = useState<'all' | 'daily' | 'weekly'>('all');
  const [reportLoading, setReportLoading] = useState(false);
  const [generating, setGenerating] = useState<'daily' | 'weekly' | null>(null);
  const [noteDialogVisible, setNoteDialogVisible] = useState(false);
  const [noteDialogType, setNoteDialogType] = useState<'daily' | 'weekly'>('daily');
  const [noteText, setNoteText] = useState('');
  const [selectedDate, setSelectedDate] = useState<Dayjs>(dayjs());
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewDetail, setPreviewDetail] = useState<ReportDetail | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [reportSectionExpanded, setReportSectionExpanded] = useState(false);

  // —— 部门周报归档 ——
  const [departmentWeeklyReports, setDepartmentWeeklyReports] = useState<DepartmentWeeklyReportItem[]>([]);
  const [departmentWeeklyTotal, setDepartmentWeeklyTotal] = useState(0);
  const [departmentWeeklyLoading, setDepartmentWeeklyLoading] = useState(false);
  const [departmentWeeklyUploading, setDepartmentWeeklyUploading] = useState(false);
  const [departmentWeeklyWeek, setDepartmentWeeklyWeek] = useState<Dayjs>(getWeekMonday(dayjs()));
  const [departmentWeeklyDepartment, setDepartmentWeeklyDepartment] = useState('');
  const [departmentWeeklyTitle, setDepartmentWeeklyTitle] = useState('');
  const [departmentWeeklyPreviewVisible, setDepartmentWeeklyPreviewVisible] = useState(false);
  const [departmentWeeklyPreview, setDepartmentWeeklyPreview] = useState<DepartmentWeeklyReportDetail | null>(null);
  const [departmentWeeklyPreviewLoading, setDepartmentWeeklyPreviewLoading] = useState(false);

  // —— 推送相关状态 ——
  const [pushingReportId, setPushingReportId] = useState<number | null>(null);
  const [pushingExpressId, setPushingExpressId] = useState<number | null>(null);

  // —— 速递相关状态 ——
  const [expressList, setExpressList] = useState<ExpressItem[]>([]);
  const [expressLoading, setExpressLoading] = useState(false);
  const [generatingExpress, setGeneratingExpress] = useState(false);

  /* —— 初始化 —— */
  useEffect(() => {
    (async () => {
      const [s, d] = await Promise.all([fetchStaff().catch(() => []), fetchDepartments().catch(() => [])]);
      setStaffList(s);
      setDepartments(d);
    })();
  }, []);

  // —— 报告相关函数 ——
  const loadReports = useCallback(async () => {
    setReportLoading(true);
    try {
      const params: Record<string, any> = { page: 1, page_size: 10 };
      if (reportTab !== 'all') params.report_type = reportTab;
      const resp = await fetchReports(params);
      setReports(resp?.items || []);
      setReportTotal(resp?.total || 0);
    } catch (err) {
      console.error('[Dashboard] 加载报告失败:', err);
    } finally {
      setReportLoading(false);
    }
  }, [reportTab]);

  useEffect(() => {
    if (reportSectionExpanded) loadReports();
  }, [reportSectionExpanded, loadReports]);

  const loadDepartmentWeeklyReports = useCallback(async () => {
    setDepartmentWeeklyLoading(true);
    try {
      const resp = await fetchDepartmentWeeklyReports({
        week_start: getWeekMonday(departmentWeeklyWeek).format('YYYY-MM-DD'),
        department: departmentWeeklyDepartment.trim() || undefined,
        page: 1,
        page_size: 20,
      });
      setDepartmentWeeklyReports(resp?.items || []);
      setDepartmentWeeklyTotal(resp?.total || 0);
    } catch {
      setDepartmentWeeklyReports([]);
      setDepartmentWeeklyTotal(0);
    } finally {
      setDepartmentWeeklyLoading(false);
    }
  }, [departmentWeeklyDepartment, departmentWeeklyWeek]);

  useEffect(() => {
    if (reportSectionExpanded) loadDepartmentWeeklyReports();
  }, [reportSectionExpanded, loadDepartmentWeeklyReports]);

  // —— 速递列表 ——
  const loadExpressList = useCallback(async () => {
    setExpressLoading(true);
    try {
      const resp = await fetchExpressList({ page: 1, page_size: 5 });
      setExpressList(resp?.items || []);
    } catch (err) {
      console.error('[Dashboard] 加载速递列表失败:', err);
    } finally {
      setExpressLoading(false);
    }
  }, []);

  useEffect(() => {
    if (reportSectionExpanded) loadExpressList();
  }, [reportSectionExpanded, loadExpressList]);

  // —— 标讯速递 ——
  const [biddingExpress, setBiddingExpress] = useState<any>(null);
  const [biddingPeriod, setBiddingPeriod] = useState<'day' | 'week' | 'month' | 'all'>('week');
  const [generatingBidding, setGeneratingBidding] = useState(false);
  const [pushingBidding, setPushingBidding] = useState(false);

  const loadBiddingExpress = useCallback(async () => {
    try {
      const resp = await getLatestBiddingExpress();
      setBiddingExpress(resp);
    } catch (err) {
      console.error('[Dashboard] 加载标讯速递失败:', err);
    }
  }, []);

  useEffect(() => {
    if (reportSectionExpanded) loadBiddingExpress();
  }, [reportSectionExpanded, loadBiddingExpress]);

  const {
    handleConvertToImage,
    handleCopyLink,
    handleDeleteDepartmentWeekly,
    handleGenerateBidding,
    handleGenerateClick,
    handleGenerateConfirm,
    handleGenerateExpress,
    handleOpenNewWindow,
    handlePreview,
    handlePreviewBidding,
    handlePreviewDepartmentWeekly,
    handlePreviewExpress,
    handlePushBidding,
    handlePushExpress,
    handlePushReport,
    handleUploadDepartmentWeekly,
  } = useDashboardReportActions({
    biddingPeriod,
    departmentWeeklyDepartment,
    departmentWeeklyTitle,
    departmentWeeklyWeek,
    loadDepartmentWeeklyReports,
    loadExpressList,
    loadReports,
    noteDialogType,
    noteText,
    previewDetail,
    selectedDate,
    setBiddingExpress,
    setDepartmentWeeklyPreview,
    setDepartmentWeeklyPreviewLoading,
    setDepartmentWeeklyPreviewVisible,
    setDepartmentWeeklyTitle,
    setDepartmentWeeklyUploading,
    setGenerating,
    setGeneratingBidding,
    setGeneratingExpress,
    setNoteDialogType,
    setNoteDialogVisible,
    setNoteText,
    setPreviewDetail,
    setPreviewLoading,
    setPreviewVisible,
    setPushingBidding,
    setPushingExpressId,
    setPushingReportId,
    setSelectedDate,
  });

  /* —— 拉取活动列表 —— */
  const loadActivities = async () => {
    setLoading(true);
    try {
      const params = {
        start_date: filter.range[0].format('YYYY-MM-DD'),
        end_date: filter.range[1].format('YYYY-MM-DD'),
        user_id: filter.userId,
        department: filter.department,
        keyword: filter.keyword || undefined,
        page: 1,
        page_size: 100,
      };
      const { list } = await fetchActivities(params);
      let filtered = list;
      if (filter.actionTypes.length > 0) {
        filtered = filtered.filter((a) => filter.actionTypes.includes(a.action_type));
      }
      if (filter.role) {
        const staffWithRole = staffList.filter((s) => s.role === filter.role).map((s) => s.id);
        filtered = filtered.filter((a) => staffWithRole.includes(a.user_id));
      }
      setActivities(filtered);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivities();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    filter.mode,
    filter.range[0]?.valueOf(),
    filter.range[1]?.valueOf(),
    filter.userId,
    filter.department,
    filter.role,
    filter.actionTypes.join(','),
    filter.keyword,
  ]);

  /* —— 模式切换 —— */
  const switchMode = useCallback((mode: 'daily' | 'weekly' | 'custom') => {
    setFilter((f) => {
      let range: [Dayjs, Dayjs];
      if (mode === 'daily') range = [f.currentDate.startOf('day'), f.currentDate.endOf('day')];
      else if (mode === 'weekly') range = [f.currentWeekStart, f.currentWeekStart.add(6, 'day').endOf('day')];
      else range = f.customRange;
      return { ...f, mode, range };
    });
  }, []);

  /* —— 日报翻页 —— */
  const goDay = useCallback((offset: number) => {
    setFilter((f) => {
      const newDate = f.currentDate.add(offset, 'day');
      return { ...f, currentDate: newDate, range: [newDate.startOf('day'), newDate.endOf('day')] };
    });
  }, []);

  /* —— 周报翻页 —— */
  const goWeek = useCallback((offset: number) => {
    setFilter((f) => {
      const newStart = f.currentWeekStart.add(offset, 'week');
      return { ...f, currentWeekStart: newStart, range: [newStart, newStart.add(6, 'day').endOf('day')] };
    });
  }, []);

  /* —— 岗位去重列表 —— */
  const roles = useMemo(() => {
    const set = new Set(staffList.map((s) => s.role).filter((role): role is string => Boolean(role)));
    return Array.from(set);
  }, [staffList]);

  /* —— 派生数据 —— */
  const weekActivities = useMemo(() => activities.length, [activities]);
  const todayActivities = useMemo(() => {
    const today = dayjs().format('YYYY-MM-DD');
    return activities.filter((a) => a.activity_date.startsWith(today)).length;
  }, [activities]);
  const activeUsers = useMemo(
    () => new Set(activities.map((a) => a.user_id)).size,
    [activities],
  );
  const followingOpps = useMemo(
    () => new Set(activities.map((a) => a.opportunity_id).filter(Boolean)).size,
    [activities],
  );

  /* —— 数据看板统计 —— */
  const [biddingStats, setBiddingStats] = useState<any>(null);
  useEffect(() => {
    fetchIntelligenceStats()
      .then(data => setBiddingStats(data))
      .catch(() => {});
  }, []);

  /* —— 行为占比（用于条形图） —— */
  const actionDistribution = useMemo(() => {
    const map = new Map<string, number>();
    activities.forEach((a) => map.set(a.action_type, (map.get(a.action_type) || 0) + 1));
    const total = activities.length || 1;
    return ACTION_TYPES.map((t) => ({
      ...t,
      count: map.get(t.value) || 0,
      pct: ((map.get(t.value) || 0) / total) * 100,
    }))
      .filter((d) => d.count > 0)
      .sort((a, b) => b.count - a.count);
  }, [activities]);

  const managementReview = useMemo(() => {
    const riskItems = activities
      .filter((a) => /风险|延期|延迟|回款|招投标|投标|待确认|未确认|介入/.test(a.summary || ''))
      .slice(0, 3);
    const topAction = actionDistribution[0];
    return {
      riskItems,
      cards: [
        { label: '团队动作', value: activities.length, unit: '条', icon: <BarChartOutlined /> },
        { label: '商机相关', value: followingOpps, unit: '个', icon: <CheckCircleOutlined /> },
        { label: '今日信号', value: biddingStats?.today_count || 0, unit: '条', icon: <FileSearchOutlined /> },
        { label: '待介入', value: riskItems.length, unit: '项', icon: <AlertOutlined /> },
      ],
      actions: [
        {
          title: '团队在忙什么',
          text: topAction ? `本期最多的是「${topAction.label}」，共 ${topAction.count} 条。` : '本期暂无可分析动作。',
        },
        {
          title: '哪些商机要介入',
          text: riskItems[0]?.summary || '当前没有明显风险关键词，建议继续关注关键商机确认记录。',
        },
        {
          title: '外部信号有什么变化',
          text: `市场洞察今日新增 ${biddingStats?.today_count || 0} 条，可同步查看标讯雷达 Agent。`,
        },
      ],
    };
  }, [activities, actionDistribution, biddingStats, followingOpps]);

  /* —— 列定义 —— */
  const columns: ProColumns<ActivityItem>[] = [
    {
      title: '日期',
      dataIndex: 'activity_date',
      width: 130,
      render: (_: any, r: ActivityItem) => (
        <span className="edl-mono cell-date">{dayjs(r.activity_date).format('MM·DD HH:mm')}</span>
      ),
    },
    {
      title: '人员',
      dataIndex: 'user_name',
      width: 120,
      render: (_: any, r: ActivityItem) => (
        <span
          className="edl-name-stamp"
          onClick={() => setDrawerStaffId(r.user_id)}
        >
          {r.user_name || '—'}
        </span>
      ),
    },
    {
      title: '行为类型',
      dataIndex: 'action_type',
      width: 130,
      render: (_: any, r: ActivityItem) => {
        const meta = getActionMeta(r.action_type);
        return (
          <span className="edl-action-chip" style={{ color: meta.ink }}>
            {meta.label}
          </span>
        );
      },
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      ellipsis: true,
      render: (_: any, r: ActivityItem) => (
        <span style={{ fontFamily: 'var(--serif)' }}>{r.summary || '—'}</span>
      ),
    },
    {
      title: '客户',
      dataIndex: 'customer_name',
      width: 160,
      render: (v: any) => v || <span style={{ color: 'var(--ink-faint)' }}>—</span>,
    },
    {
      title: '商机',
      dataIndex: 'opportunity_id',
      width: 120,
      render: (v: any) => (v ? <Tag color="volcano">#{v}</Tag> : <span style={{ color: 'var(--ink-faint)' }}>—</span>),
    },
  ];

  /* —— 分组视图 —— */
  const groupedByStaff = useMemo(() => {
    const map = new Map<string, ActivityItem[]>();
    activities.forEach((a) => {
      const key = a.user_name || '未署名';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(a);
    });
    return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
  }, [activities]);

  const groupedByOpp = useMemo(() => {
    const map = new Map<string, ActivityItem[]>();
    activities.forEach((a) => {
      const key = a.opportunity_id ? `商机 #${a.opportunity_id}` : '— 无关联商机';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(a);
    });
    return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
  }, [activities]);

  const dashboardViewContext = {
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
  };

  return <DashboardView ctx={dashboardViewContext} />;
};

export default Dashboard;
