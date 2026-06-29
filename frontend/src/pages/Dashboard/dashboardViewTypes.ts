import React from 'react';
import { ProColumns } from '@ant-design/pro-components';
import { Dayjs } from 'dayjs';
import {
  ActivityItem,
  DepartmentWeeklyReportDetail,
  DepartmentWeeklyReportItem,
  ExpressItem,
  ReportDetail,
  ReportItem,
  Staff,
} from '@/services/api';
import { FilterState } from './dashboardShared';

type ReviewCard = { label: string; value: number; unit: string; icon: React.ReactNode };
type ReviewAction = { title: string; text: string };
type ActionDistributionItem = { value: string; label: string; ink: string; count: number; pct: number };

export type DashboardViewContext = {
  [key: string]: any;
  filter: FilterState;
  setFilter: React.Dispatch<React.SetStateAction<FilterState>>;
  activities: ActivityItem[];
  staffList: Staff[];
  roles: string[];
  departments: string[];
  managementReview: { cards: ReviewCard[]; actions: ReviewAction[] };
  actionDistribution: ActionDistributionItem[];
  reports: ReportItem[];
  departmentWeeklyReports: DepartmentWeeklyReportItem[];
  expressList: ExpressItem[];
  groupedByStaff: Array<[string, ActivityItem[]]>;
  groupedByOpp: Array<[string, ActivityItem[]]>;
  columns: ProColumns<ActivityItem>[];
  reportTotal: number;
  reportLoading: boolean;
  reportSectionExpanded: boolean;
  departmentWeeklyTotal: number;
  departmentWeeklyWeek: Dayjs;
  departmentWeeklyPreview?: DepartmentWeeklyReportDetail | null;
  previewDetail?: ReportDetail | null;
};
