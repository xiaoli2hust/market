import React from 'react';
import { Button, Empty, Segmented, Space, Spin } from 'antd';
import { EyeOutlined, FileSearchOutlined, RobotOutlined } from '@ant-design/icons';
import {
  AgentSection,
  DistributionList,
  EvidenceRecordList,
  InsightPanel,
  MetricGrid,
  TopSignalList,
} from './components';
import { formatWanAmount, uniqueTexts } from './intelligenceMeta';

type IntelligenceContext = Record<string, any>;

export const BiddingAgentView: React.FC<{ ctx: IntelligenceContext }> = ({ ctx }) => {
  const { analysisLoading, analysisPeriod, setAnalysisPeriod, openDataCenter, biddingAnalysis } = ctx;
  return (
    <Spin spinning={analysisLoading}>
      <AgentSection
        eyebrow="Bidding Radar Agent"
        title="标讯雷达 Agent"
        desc="不是把标讯堆给销售，而是先判断哪些值得关注、集中在哪些行业场景、由哪些关键词触发。"
        actions={(
          <Space>
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
            <Button icon={<FileSearchOutlined />} onClick={() => openDataCenter('bidding')}>
              标讯雷达明细
            </Button>
          </Space>
        )}
      >
        {biddingAnalysis ? (
          <>
            <MetricGrid
              metrics={[
                ['有效标讯', biddingAnalysis.summary.relevant, '条'],
                ['平均贴合度', biddingAnalysis.summary.avg_score, '分'],
                ['识别金额', formatWanAmount(biddingAnalysis.summary.amount_total_wan), ''],
                ['过滤噪音', biddingAnalysis.summary.ignored, '条'],
              ]}
            />
            <div className="intel-agent-grid">
              <InsightPanel title="当前判断">
                {(biddingAnalysis.findings || []).map((text: string) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="建议动作">
                {(biddingAnalysis.recommendations || []).map((text: string) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="行业/场景分布">
                <DistributionList items={biddingAnalysis.distribution.topics} tone="red" />
                <DistributionList items={biddingAnalysis.distribution.customer_types} />
              </InsightPanel>
              <InsightPanel title="关键词触发分布">
                <DistributionList items={biddingAnalysis.distribution.keywords || []} tone="red" />
              </InsightPanel>
            </div>
            <TopSignalList
              title="高贴合标讯关注"
              items={biddingAnalysis.top_items || []}
              emptyText="暂无高贴合标讯"
              onOpenData={() => openDataCenter('bidding')}
            />
            <EvidenceRecordList
              title="分析证据记录"
              items={biddingAnalysis.evidence_records || []}
              onOpenData={() => openDataCenter('bidding')}
            />
          </>
        ) : (
          <Empty description="暂无标讯分析数据" />
        )}
      </AgentSection>
    </Spin>
  );
};


export const PolicyMarketAgentView: React.FC<{ ctx: IntelligenceContext }> = ({ ctx }) => {
  const { analysisLoading, analysisPeriod, setAnalysisPeriod, openDataCenter, policyAnalysis, marketAnalysis } = ctx;
  const recommendations = uniqueTexts(policyAnalysis?.recommendations, marketAnalysis?.recommendations);
  const findings = uniqueTexts(policyAnalysis?.findings, marketAnalysis?.findings);
  return (
    <Spin spinning={analysisLoading}>
        <AgentSection
          eyebrow="Policy & Market Tracking Agent"
          title="政策与市场跟踪 Agent"
          desc="只分析高相关政策和市场线索，回答市场导向、客户方向和应该沉淀成什么打法。"
          actions={(
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
          )}
        >
          <MetricGrid
            metrics={[
              ['高相关政策', policyAnalysis?.summary.relevant || 0, '条'],
              ['市场线索', marketAnalysis?.summary.relevant || 0, '条'],
              ['政策评分', policyAnalysis?.summary.avg_score || 0, '分'],
              ['市场评分', marketAnalysis?.summary.avg_score || 0, '分'],
            ]}
          />
          <div className="intel-agent-grid">
            <InsightPanel title="市场导向">
              {findings.length ? findings.slice(0, 5).map((text: string) => <p key={text}>{text}</p>) : <p>暂无高相关政策与市场信号。</p>}
            </InsightPanel>
            <InsightPanel title="Agent 建议">
              {recommendations.length ? recommendations.slice(0, 5).map((text: string) => <p key={text}>{text}</p>) : <p>先补充政策和市场采集源，再形成导向判断。</p>}
            </InsightPanel>
            <InsightPanel title="政策主题">
              <DistributionList items={policyAnalysis?.distribution.topics || []} tone="cyan" />
            </InsightPanel>
            <InsightPanel title="市场关键词">
              <DistributionList items={marketAnalysis?.distribution.keywords || []} />
            </InsightPanel>
          </div>
          <TopSignalList
            title="重点政策与市场信号"
            items={[...(policyAnalysis?.top_items || []), ...(marketAnalysis?.top_items || [])].slice(0, 8)}
            emptyText="暂无重点政策或市场信号"
            onOpenData={() => openDataCenter('policy')}
          />
          <EvidenceRecordList
            title="导向判断证据"
            items={[...(policyAnalysis?.evidence_records || []), ...(marketAnalysis?.evidence_records || [])].slice(0, 12)}
            onOpenData={() => openDataCenter('policy')}
          />
        </AgentSection>
    </Spin>
  );
};


export const CompetitorAgentView: React.FC<{ ctx: IntelligenceContext }> = ({ ctx }) => {
  const { analysisLoading, analysisPeriod, setAnalysisPeriod, openDataCenter, competitorAnalysis } = ctx;
  return (
    <Spin spinning={analysisLoading}>
      <AgentSection
        eyebrow="Competitor Monitoring Agent"
        title="竞对监控 Agent"
        desc="围绕竞对中标、重点客户案例、产品动作和区域推进做研判，输出应该关注什么、如何调整打法。"
        actions={(
          <Space>
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
            <Button icon={<EyeOutlined />} onClick={() => openDataCenter('competitor')}>
              竞对信号明细
            </Button>
          </Space>
        )}
      >
        {competitorAnalysis ? (
          <>
            <MetricGrid
              metrics={[
                ['有效竞对信号', competitorAnalysis.summary.relevant, '条'],
                ['平均影响评分', competitorAnalysis.summary.avg_score, '分'],
                ['动作类型', competitorAnalysis.distribution.actions.length, '类'],
                ['证据记录', competitorAnalysis.summary.evidence_count || 0, '条'],
              ]}
            />
            <div className="intel-agent-grid">
              <InsightPanel title="竞对判断">
                {(competitorAnalysis.findings || []).map((text: string) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="建议动作">
                {(competitorAnalysis.recommendations || []).map((text: string) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="竞对主题">
                <DistributionList items={competitorAnalysis.distribution.topics || []} />
              </InsightPanel>
              <InsightPanel title="客户与区域">
                <DistributionList items={competitorAnalysis.distribution.customer_types || []} />
                <DistributionList items={competitorAnalysis.distribution.regions || []} />
              </InsightPanel>
            </div>
            <TopSignalList
              title="重点竞对动作"
              items={competitorAnalysis.top_items || []}
              emptyText="暂无重点竞对信号"
              onOpenData={() => openDataCenter('competitor')}
            />
            <EvidenceRecordList
              title="竞对判断证据"
              items={competitorAnalysis.evidence_records || []}
              onOpenData={() => openDataCenter('competitor')}
            />
          </>
        ) : (
          <Empty description="暂无竞对分析数据" />
        )}
      </AgentSection>
    </Spin>
  );
};


export const IndustryKnowledgeAgentView: React.FC<{ ctx: IntelligenceContext }> = ({ ctx }) => {
  const { analysisLoading, analysisPeriod, setAnalysisPeriod, openDataCenter, aiAnalysis } = ctx;
  return (
    <Spin spinning={analysisLoading}>
      <AgentSection
        eyebrow="Industry Knowledge Agent"
        title="行业知识 Agent"
        desc="沉淀 Agent、空间数据、GIS、地址治理、数据治理和行业技术动态，用于售前话术、方案素材和产品方向判断。"
        actions={(
          <Space>
            <Segmented
              value={analysisPeriod}
              onChange={(value) => setAnalysisPeriod(value as 'week' | 'month')}
              options={[{ label: '本周', value: 'week' }, { label: '本月', value: 'month' }]}
            />
            <Button icon={<RobotOutlined />} onClick={() => openDataCenter('ai')}>
              知识素材明细
            </Button>
          </Space>
        )}
      >
        {aiAnalysis ? (
          <>
            <MetricGrid
              metrics={[
                ['有效知识素材', aiAnalysis.summary.relevant, '条'],
                ['平均相关度', aiAnalysis.summary.avg_score, '分'],
                ['主题数量', aiAnalysis.distribution.topics.length, '类'],
                ['证据记录', aiAnalysis.summary.evidence_count || 0, '条'],
              ]}
            />
            <div className="intel-agent-grid">
              <InsightPanel title="知识判断">
                {(aiAnalysis.findings || []).map((text: string) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="沉淀建议">
                {(aiAnalysis.recommendations || []).map((text: string) => <p key={text}>{text}</p>)}
              </InsightPanel>
              <InsightPanel title="主题分布">
                <DistributionList items={aiAnalysis.distribution.topics || []} />
              </InsightPanel>
              <InsightPanel title="关键词与动作">
                <DistributionList items={aiAnalysis.distribution.keywords || []} />
                <DistributionList items={aiAnalysis.distribution.actions || []} />
              </InsightPanel>
            </div>
            <TopSignalList
              title="重点知识素材"
              items={aiAnalysis.top_items || []}
              emptyText="暂无重点行业知识"
              onOpenData={() => openDataCenter('ai')}
            />
            <EvidenceRecordList
              title="知识判断证据"
              items={aiAnalysis.evidence_records || []}
              onOpenData={() => openDataCenter('ai')}
            />
          </>
        ) : (
          <Empty description="暂无行业知识分析数据" />
        )}
      </AgentSection>
    </Spin>
  );
};
