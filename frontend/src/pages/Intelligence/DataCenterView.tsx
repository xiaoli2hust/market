import React, { useMemo } from 'react';
import { Button, Empty, Input, Segmented, Table, Tag } from 'antd';
import { LinkOutlined, ReloadOutlined, RobotOutlined, SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import type { IntelligenceItem } from '@/services/api';
import { WorkbenchStatusRail } from '@/components/workbench';
import {
  CATEGORY_META,
  DataSortBy,
  DataSortOrder,
  PAGE_SIZE,
  itemAmountText,
  itemAmountWan,
  itemSourceText,
  tableSortOrder,
} from './intelligenceMeta';

type IntelligenceContext = Record<string, any>;

export const DataCenterView: React.FC<{ ctx: IntelligenceContext }> = ({ ctx }) => {
  const {
    items, dataCategory, crawlerStatus, crawling, canRunAgents, dataCategoryOptions,
    searchValue, setSearchValue, handleSearch, handleCrawlAll, setDataCategory,
    setSortBy, setSortOrder, setPage, sortBy, sortOrder, loading, page, total,
    handleTableChange,
  } = ctx;

  const dataQualityStats = useMemo(() => {
    const withDate = items.filter((item: IntelligenceItem) => !!item.published_at).length;
    const withAmount = items.filter((item: IntelligenceItem) => itemAmountWan(item) > 0).length;
    const withSource = items.filter((item: IntelligenceItem) => !!item.source_url).length;
    return [
      { label: '当前页', value: `${items.length} 条`, status: items.length ? 'good' as const : 'muted' as const },
      { label: '有发布日期', value: `${withDate} 条`, meta: `${items.length ? Math.round((withDate / items.length) * 100) : 0}%`, status: withDate ? 'good' as const : 'warn' as const },
      { label: '有金额', value: `${withAmount} 条`, meta: dataCategory === 'bidding' ? '标讯重点字段' : '非标讯可为空', status: withAmount ? 'good' as const : 'warn' as const },
      { label: '可追溯原文', value: `${withSource} 条`, status: withSource ? 'good' as const : 'warn' as const },
    ];
  }, [items, dataCategory]);

  const dataColumns = useMemo(() => [
    {
      title: '信号',
      dataIndex: 'title',
      key: 'title',
      render: (_: string, item: IntelligenceItem) => {
        const meta = CATEGORY_META[item.category] || CATEGORY_META.news;
        const keywords = item.extra_data?.matched_keywords || [];
        return (
          <div className="intel-data-title">
            <div>
              <Tag color={meta.color} icon={meta.icon}>{meta.label}</Tag>
              <strong onClick={() => item.source_url && window.open(item.source_url, '_blank', 'noopener,noreferrer')}>{item.title}</strong>
            </div>
            {(item.summary || item.content) && <p>{item.summary || item.content?.slice(0, 120)}</p>}
            {!!keywords.length && (
              <div className="intel-data-keywords">
                {keywords.slice(0, 4).map((kw: string) => <Tag key={kw}>{kw}</Tag>)}
              </div>
            )}
          </div>
        );
      },
    },
    {
      title: '发布日期',
      dataIndex: 'published_at',
      key: 'published_at',
      width: 124,
      sorter: true,
      sortOrder: tableSortOrder(sortBy === 'published_at', sortOrder),
      render: (_: string, item: IntelligenceItem) => (
        <div className="intel-data-date">
          <strong>{item.published_at ? dayjs(item.published_at).format('YYYY-MM-DD') : '未标日期'}</strong>
          {!item.published_at && item.created_at && <span>入库 {dayjs(item.created_at).format('MM-DD')}</span>}
        </div>
      ),
    },
    {
      title: '金额',
      dataIndex: 'amount_wan',
      key: 'amount_wan',
      width: 112,
      align: 'right' as const,
      sorter: true,
      sortOrder: tableSortOrder(sortBy === 'amount', sortOrder),
      render: (_: number, item: IntelligenceItem) => (
        <span className={itemAmountWan(item) > 0 ? 'intel-data-amount strong' : 'intel-data-amount'}>
          {itemAmountText(item)}
        </span>
      ),
    },
    {
      title: '相关度',
      dataIndex: 'relevance_score',
      key: 'relevance_score',
      width: 96,
      align: 'right' as const,
      sorter: true,
      sortOrder: tableSortOrder(sortBy === 'relevance', sortOrder),
      render: (score?: number) => (score == null ? '—' : <span className="edl-mono">{Math.round(score)}</span>),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 170,
      render: (_: string, item: IntelligenceItem) => (
        <div className="intel-data-source">
          <span>{itemSourceText(item)}</span>
          {item.source_url && <LinkOutlined onClick={() => window.open(item.source_url, '_blank', 'noopener,noreferrer')} />}
        </div>
      ),
    },
  ], [sortBy, sortOrder]);

  return (
    <div className="intel-data-center">
      <div className="intel-crawler-bar">
        <div className="crawler-bar-label">
          <RobotOutlined /> 采集状态
        </div>
        <div className="crawler-bar-items">
          {crawlerStatus.map((cs: { name: string; status: string; label: string; total_collected: number }) => (
            <div key={cs.name} className="crawler-bar-item">
              <span className="crawler-dot" data-status={cs.status} />
              <span className="crawler-name">{cs.label}</span>
              <span className="crawler-count edl-mono">{cs.total_collected}</span>
            </div>
          ))}
        </div>
        <Button
          icon={<ReloadOutlined spin={crawling} />}
          size="small"
          onClick={handleCrawlAll}
          loading={crawling}
          disabled={!canRunAgents}
          title={!canRunAgents ? '当前账号无采集管理权限' : undefined}
        >
          重新采集
        </Button>
      </div>

      <div className="intel-data-toolbar">
        <div className="intel-type-switch">
          <span>数据类型</span>
          <Segmented
            value={dataCategory}
            onChange={(key) => {
              const nextCategory = String(key);
              setDataCategory(nextCategory);
              setSortBy(nextCategory === 'bidding' ? 'amount' : 'published_at');
              setSortOrder('desc');
              setPage(1);
            }}
            options={dataCategoryOptions}
          />
        </div>
        <Segmented
          className="intel-data-sort"
          value={`${sortBy}:${sortOrder}`}
          onChange={(value) => {
            const [nextSortBy, nextSortOrder] = String(value).split(':') as [DataSortBy, DataSortOrder];
            setSortBy(nextSortBy);
            setSortOrder(nextSortOrder);
            setPage(1);
          }}
          options={[
            { label: '最新优先', value: 'published_at:desc' },
            { label: '金额最高', value: 'amount:desc' },
            { label: '相关度最高', value: 'relevance:desc' },
          ]}
        />
        <Input.Search
          className="intel-data-search"
          placeholder="搜索标题、摘要..."
          value={searchValue}
          onChange={(e) => setSearchValue(e.target.value)}
          onSearch={handleSearch}
          enterButton={<SearchOutlined />}
          allowClear
          />
        </div>

      <WorkbenchStatusRail items={dataQualityStats} />

      <Table<IntelligenceItem>
        className="intel-data-table"
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={dataColumns}
        scroll={{ x: 820 }}
        onChange={handleTableChange}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          showSizeChanger: false,
          showTotal: (count) => `共 ${count} 条`,
        }}
        locale={{ emptyText: <Empty description="暂无市场数据" /> }}
      />
    </div>
  );
};
