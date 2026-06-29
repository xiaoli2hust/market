import React from 'react';
import { DashboardActivitySection } from './DashboardActivitySection';
import { DashboardBiddingExpressSection } from './DashboardBiddingExpressSection';
import { DashboardExpressSection } from './DashboardExpressSection';
import { DashboardOverlays } from './DashboardOverlays';
import { DashboardOverviewSections } from './DashboardOverviewSections';
import { DashboardReportSection } from './DashboardReportSection';
import { DashboardViewContext } from './dashboardViewTypes';
import { DashboardWeeklyArchiveSection } from './DashboardWeeklyArchiveSection';

export const DashboardView: React.FC<{ ctx: DashboardViewContext }> = ({ ctx }) => (
  <div className="dash">
    <DashboardOverviewSections ctx={ctx} />
    <DashboardReportSection ctx={ctx} />
    <DashboardWeeklyArchiveSection ctx={ctx} />
    <DashboardExpressSection ctx={ctx} />
    <DashboardBiddingExpressSection ctx={ctx} />
    <DashboardActivitySection ctx={ctx} />
    <DashboardOverlays ctx={ctx} />
  </div>
);
