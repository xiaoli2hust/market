import React, { useCallback, useEffect, useMemo, useState } from 'react';
declare global {
  interface Window {
    html2canvas: any;
  }
}
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
  message,
} from 'antd';
import {
  LeftOutlined,
  ReloadOutlined,
  RightOutlined,
  SearchOutlined,
  FileTextOutlined,
  CopyOutlined,
  EyeOutlined,
  ExportOutlined,
  PlusOutlined,
  SendOutlined,
  CheckCircleOutlined,
  FileSearchOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import { ProTable, ProColumns } from '@ant-design/pro-components';
import dayjs, { Dayjs } from 'dayjs';
import {
  ActivityItem,
  DashboardStats,
  fetchActivities,
  fetchDashboardStats,
  fetchDepartments,
  fetchStaff,
  Staff,
  fetchReports,
  fetchReportDetail,
  generateReport,
  pushReport,
  pushExpress,
  fetchExpressList,
  generateExpress,
  generateBiddingExpress,
  getLatestBiddingExpress,
  pushBiddingExpress,
  ReportItem,
  ReportDetail,
  ExpressItem,
} from '@/services/api';
import { ACTION_TYPES, getActionMeta } from '@/constants/actionTypes';
import StaffDetailDrawer from '@/components/StaffDetailDrawer';
import './dashboard.less';

const { RangePicker } = DatePicker;
const { Title } = Typography;

interface FilterState {
  mode: 'daily' | 'weekly' | 'custom';
  currentDate: Dayjs;
  currentWeekStart: Dayjs;
  customRange: [Dayjs, Dayjs];
  range: [Dayjs, Dayjs];
  userId?: number;
  department?: string;
  role?: string;
  actionTypes: string[];
  keyword: string;
}

const Dashboard: React.FC = () => {
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

  const [stats, setStats] = useState<DashboardStats | null>(null);
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
    fetchDashboardStats()
      .then(setStats)
      .catch(() => setStats(null));
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
    } catch {
      /* silent */
    } finally {
      setReportLoading(false);
    }
  }, [reportTab]);

  useEffect(() => {
    if (reportSectionExpanded) loadReports();
  }, [reportSectionExpanded, loadReports]);

  const handleGenerateClick = (type: 'daily' | 'weekly') => {
    setNoteDialogType(type);
    setNoteText('');
    setSelectedDate(type === 'daily' ? dayjs() : dayjs().startOf('week'));
    setNoteDialogVisible(true);
  };

  const handleGenerateConfirm = async (autoPush: boolean = false) => {
    setNoteDialogVisible(false);
    setGenerating(noteDialogType);
    try {
      const date = selectedDate.format('YYYY-MM-DD');
      const result = await generateReport({
        report_type: noteDialogType,
        date,
        note: noteText.trim() || undefined,
      });
      message.success(noteDialogType === 'daily' ? '日报生成成功' : '周报生成成功');
      loadReports();

      // 自动生成后推送
      if (autoPush && result?.id) {
        const pushResult = await pushReport(result.id, { base_url: window.location.origin });
        if (pushResult.success) {
          message.success('✅ 已自动推送到钉钉');
        } else {
          message.warning('⚠️ 生成成功，但推送失败：' + pushResult.message);
        }
      }
    } catch {
      message.error('生成报告失败，请稍后重试');
    } finally {
      setGenerating(null);
    }
  };

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

  const handleCopyLink = (shareUrl: string) => {
    const fullUrl = window.location.origin + shareUrl;
    navigator.clipboard.writeText(fullUrl).then(
      () => message.success('链接已复制'),
      () => message.error('复制失败，请手动复制'),
    );
  };

  const handleOpenNewWindow = (shareUrl: string) => {
    window.open(window.location.origin + shareUrl, '_blank');
  };

  // —— 报告转图片 ——
  const handleConvertToImage = async () => {
    if (!previewDetail?.html_content) return;

    try {
      // 动态加载 html2canvas
      if (!window.html2canvas) {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js';
        document.head.appendChild(script);
        await new Promise((resolve) => {
          script.onload = resolve;
        });
      }

      // 创建临时容器渲染 HTML
      const container = document.createElement('div');
      container.innerHTML = previewDetail.html_content;
      container.style.position = 'absolute';
      container.style.left = '-9999px';
      container.style.width = '900px';
      document.body.appendChild(container);

      // 等待图片加载
      await new Promise((resolve) => setTimeout(resolve, 500));

      // 转换为 canvas
      const canvas = await window.html2canvas(container, {
        scale: 2,
        useCORS: true,
        backgroundColor: '#f5f7fa',
      });

      // 下载图片
      const link = document.createElement('a');
      link.download = `${previewDetail.title}_${previewDetail.report_date}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();

      // 清理
      document.body.removeChild(container);
      message.success('图片已下载');
    } catch (err) {
      message.error('转换失败，请重试');
    }
  };

  // —— 推送报告到钉钉 ——
  const handlePushReport = async (reportId: number) => {
    setPushingReportId(reportId);
    try {
      const result = await pushReport(reportId, { base_url: window.location.origin });
      if (result.success) {
        message.success('推送成功');
        loadReports();
      } else {
        message.error(result.message || '推送失败');
      }
    } catch {
      message.error('推送失败，请检查钉钉配置');
    } finally {
      setPushingReportId(null);
    }
  };

  // —— 推送速递到钉钉 ——
  const handlePushExpress = async (expressId: number) => {
    setPushingExpressId(expressId);
    try {
      const result = await pushExpress(expressId, { base_url: window.location.origin });
      if (result.success) {
        message.success('速递推送成功');
        loadExpressList();
      } else {
        message.error(result.message || '推送失败');
      }
    } catch {
      message.error('推送失败，请检查钉钉配置');
    } finally {
      setPushingExpressId(null);
    }
  };

  // —— 速递列表 ——
  const loadExpressList = useCallback(async () => {
    setExpressLoading(true);
    try {
      const resp = await fetchExpressList({ page: 1, page_size: 5 });
      setExpressList(resp?.items || []);
    } catch {
      /* silent */
    } finally {
      setExpressLoading(false);
    }
  }, []);

  useEffect(() => {
    if (reportSectionExpanded) loadExpressList();
  }, [reportSectionExpanded, loadExpressList]);

  // —— 生成今日速递 ——
  const handleGenerateExpress = async () => {
    setGeneratingExpress(true);
    try {
      await generateExpress({ date: dayjs().format('YYYY-MM-DD') });
      message.success('今日速递生成成功');
      loadExpressList();
    } catch {
      message.error('生成速递失败');
    } finally {
      setGeneratingExpress(false);
    }
  };

  // —— 标讯速递 ——
  const [biddingExpress, setBiddingExpress] = useState<any>(null);
  const [generatingBidding, setGeneratingBidding] = useState(false);
  const [pushingBidding, setPushingBidding] = useState(false);

  const loadBiddingExpress = useCallback(async () => {
    try {
      const resp = await getLatestBiddingExpress();
      setBiddingExpress(resp);
    } catch { /* silent */ }
  }, []);

  const handleGenerateBidding = async () => {
    setGeneratingBidding(true);
    try {
      const resp = await generateBiddingExpress({});
      message.success(resp.message || '标讯速递生成成功');
      setBiddingExpress(resp);
    } catch {
      message.error('生成标讯速递失败');
    } finally {
      setGeneratingBidding(false);
    }
  };

  const handlePushBidding = async () => {
    setPushingBidding(true);
    try {
      const resp = await pushBiddingExpress({ base_url: window.location.origin });
      if (resp.success) {
        message.success(`标讯速递已推送：${resp.total} 条`);
      } else {
        message.error(resp.message || '推送失败');
      }
    } catch {
      message.error('推送失败，请检查钉钉配置');
    } finally {
      setPushingBidding(false);
    }
  };

  useEffect(() => {
    if (reportSectionExpanded) loadBiddingExpress();
  }, [reportSectionExpanded, loadBiddingExpress]);

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
  }, [filter]);

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
    const set = new Set(staffList.map((s) => s.role).filter(Boolean));
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
    // 获取标讯统计
    fetch('/api/intelligence/stats')
      .then(r => r.json())
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

  return (
    <div className="dash">
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
              onClick={() => handleGenerateClick('daily')}
              size="small"
            >
              生成日报
            </Button>
            <Button
              icon={<PlusOutlined />}
              loading={generating === 'weekly'}
              onClick={() => handleGenerateClick('weekly')}
              size="small"
            >
              生成周报
            </Button>
            <a
              className="dash-report-toggle"
              onClick={() => setReportSectionExpanded(!reportSectionExpanded)}
            >
              {reportSectionExpanded ? '收起历史 ▲' : '历史报告 ▼'}
            </a>
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
                      render: (text: string) => (
                        <span style={{ fontFamily: 'var(--serif)', fontWeight: 600, fontSize: 13 }}>
                          {text || '—'}
                        </span>
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
                          {record.push_status === 'pushed' ? (
                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
                              <CheckCircleOutlined /> 已推送
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
                                <SendOutlined /> 推送
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
                            onClick={() => window.open(window.location.origin + `/re/${record.id}`, '_blank')}
                          >
                            <EyeOutlined /> 预览
                          </a>
                          {record.push_status === 'pushed' ? (
                            <span style={{ color: 'var(--ink-faint)', fontSize: 12 }}>
                              <CheckCircleOutlined /> 已推送
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
                                <SendOutlined /> 推送
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

      {/* 标讯速递 */}
      {reportSectionExpanded && (
        <div className="dash-report edl-rise edl-rise-3d" style={{ marginTop: 16 }}>
          <div className="dash-report-bar">
            <div className="dash-report-left">
              <FileSearchOutlined className="dash-report-icon" />
              <div>
                <div className="edl-eyebrow" style={{ marginBottom: 2 }}>标讯速递</div>
                <span style={{ fontSize: 13, color: 'var(--ink-faint)' }}>
                  剑鱼标讯 API 数据整合，按类型分组 + 高金额/重点匹配置顶
                  {biddingExpress?.total && <span className="edl-mono"> · {biddingExpress.total} 条</span>}
                </span>
              </div>
            </div>
            <Space size={8}>
              <Button icon={<ReloadOutlined />} loading={generatingBidding} onClick={handleGenerateBidding} size="small">
                生成标讯速递
              </Button>
              {biddingExpress?.status === 'ok' && (
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
                <Button size="small" onClick={() => window.open('/bidding-express/preview', '_blank')}>
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
            </div>
          )}
          {biddingExpress?.status === 'empty' && (
            <div style={{ padding: '12px 16px', fontSize: 13, color: 'var(--ink-faint)' }}>
              点击「生成标讯速递」从剑鱼 API 拉取并整合数据
            </div>
          )}
        </div>
      )}

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
          <Button onClick={() => handleGenerateConfirm(false)} loading={generating !== null}>
            仅生成
          </Button>
          <Button type="primary" onClick={() => handleGenerateConfirm(true)} loading={generating !== null}>
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
              srcDoc={previewDetail.html_content}
              className="dash-preview-iframe"
              title="报告预览"
            />
          ) : (
            !previewLoading && <Empty description="暂无内容" />
          )}
        </Spin>
      </Modal>
    </div>
  );
};

const StatCell: React.FC<{
  label: string;
  value: number;
  unit?: string;
  highlight?: boolean;
}> = ({ label, value, unit, highlight }) => (
  <div className={`dash-stat edl-card ${highlight ? 'is-highlight' : ''}`}>
    <div className="edl-stat-label">{label}</div>
    <div className="dash-stat-value">
      <span className="edl-stat-num">{value}</span>
      {unit && <span className="dash-stat-unit">{unit}</span>}
    </div>
  </div>
);

export default Dashboard;
