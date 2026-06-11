import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Input,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import { LeftOutlined, ReloadOutlined, RightOutlined, SearchOutlined } from '@ant-design/icons';
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
    return {
      mode: 'daily',
      currentDate: today,
      currentWeekStart: today.startOf('week'),
      customRange: [today.startOf('month'), today],
      range: [today.startOf('day'), today.endOf('day')],
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
          <div className="edl-eyebrow">头版 · 日报看板</div>
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

          {/* 日报模式：← 日期 → */}
          {filter.mode === 'daily' && (
            <Space>
              <Button icon={<LeftOutlined />} onClick={() => goDay(-1)} type="text" />
              <span style={{ fontWeight: 600, minWidth: 120, textAlign: 'center', display: 'inline-block' }}>
                {filter.currentDate.format('YYYY/MM/DD')}
                {filter.currentDate.isSame(dayjs(), 'day') && <Tag color="red" style={{ marginLeft: 4 }}>今天</Tag>}
              </span>
              <Button icon={<RightOutlined />} onClick={() => goDay(1)} type="text"
                disabled={filter.currentDate.isSame(dayjs(), 'day')} />
            </Space>
          )}

          {/* 周报模式：← 周 → */}
          {filter.mode === 'weekly' && (
            <Space>
              <Button icon={<LeftOutlined />} onClick={() => goWeek(-1)} type="text" />
              <span style={{ fontWeight: 600, minWidth: 180, textAlign: 'center', display: 'inline-block' }}>
                {filter.currentWeekStart.format('M/D')} - {filter.currentWeekStart.add(6, 'day').format('M/D')}
              </span>
              <Button icon={<RightOutlined />} onClick={() => goWeek(1)} type="text"
                disabled={filter.currentWeekStart.isSame(dayjs().startOf('week'))} />
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
                      {items.slice(0, 8).map((it) => (
                        <li key={it.id}>
                          <span
                            className="edl-action-chip"
                            style={{ color: getActionMeta(it.action_type).ink }}
                          >
                            {getActionMeta(it.action_type).label}
                          </span>
                          <span className="dash-group-summary">{it.summary || '—'}</span>
                          <span className="edl-mono dash-group-date">
                            {dayjs(it.activity_date).format('MM·DD')}
                          </span>
                        </li>
                      ))}
                      {items.length > 8 && (
                        <li className="dash-group-more">
                          …还有 {items.length - 8} 条
                        </li>
                      )}
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
