import React, { useEffect, useState } from 'react';
import { Drawer, Empty, Skeleton, Tag } from 'antd';
import dayjs from 'dayjs';
import { fetchStaffDetail, StaffDetail } from '@/services/api';
import { getActionMeta } from '@/constants/actionTypes';
import './staff-drawer.less';

interface Props {
  staffId: number | null;
  onClose: () => void;
}

const StaffDetailDrawer: React.FC<Props> = ({ staffId, onClose }) => {
  const [data, setData] = useState<StaffDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (staffId == null) {
      setData(null);
      return;
    }
    setLoading(true);
    fetchStaffDetail(staffId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [staffId]);

  return (
    <Drawer
      open={staffId != null}
      onClose={onClose}
      width={520}
      closable={false}
      title={null}
      className="staff-drawer"
      styles={{ body: { padding: 0 } }}
    >
      {loading || !data ? (
        <div style={{ padding: 32 }}>
          <Skeleton active paragraph={{ rows: 6 }} />
        </div>
      ) : (
        <div className="sd">
          {/* 头部刊头 */}
          <div className="sd-head">
            <div className="edl-eyebrow">人物 · Staff Profile</div>
            <h2 className="sd-name">
              <span className="seal">{data.staff.name?.[0] || '?'}</span>
              {data.staff.name}
            </h2>
            <div className="sd-meta">
              <span className="edl-mono">
                {data.staff.department || '—'} · {data.staff.role || '—'}
              </span>
              <span className="sd-close" onClick={onClose}>
                关闭 ×
              </span>
            </div>
          </div>

          <hr className="edl-rule-strong" />

          {/* 三联指标 */}
          <div className="sd-stats">
            <div className="sd-stat">
              <div className="edl-stat-num">{data.active_days}</div>
              <div className="edl-eyebrow">活跃天数</div>
            </div>
            <div className="sd-stat sd-stat-accent">
              <div className="edl-stat-num">{data.visit_count}</div>
              <div className="edl-eyebrow">拜访次数</div>
            </div>
            <div className="sd-stat">
              <div className="edl-stat-num">{data.opportunity_count}</div>
              <div className="edl-eyebrow">跟进商机</div>
            </div>
          </div>

          <hr className="edl-rule" />

          {/* 近期活动 */}
          <div className="sd-section">
            <div className="edl-eyebrow">近期 · Recent Activities</div>
            <h3 className="sd-section-title">最近 50 条营销动作</h3>

            {data.recent_activities.length === 0 ? (
              <Empty description="暂无动作记录" />
            ) : (
              <ul className="sd-feed">
                {data.recent_activities.map((a) => {
                  const meta = getActionMeta(a.action_type);
                  return (
                    <li key={a.id}>
                      <div className="sd-feed-time">
                        <span className="edl-display">{dayjs(a.activity_date).format('DD')}</span>
                        <span className="edl-mono">{dayjs(a.activity_date).format('MM·HH:mm')}</span>
                      </div>
                      <div className="sd-feed-bar" style={{ background: meta.ink }} />
                      <div className="sd-feed-body">
                        <div className="sd-feed-row1">
                          <span className="edl-action-chip" style={{ color: meta.ink }}>
                            {meta.label}
                          </span>
                          {a.customer_name && (
                            <span className="sd-customer">@ {a.customer_name}</span>
                          )}
                          {a.opportunity_id && <Tag color="volcano">#{a.opportunity_id}</Tag>}
                        </div>
                        <div className="sd-feed-summary">{a.summary || '—'}</div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
};

export default StaffDetailDrawer;
