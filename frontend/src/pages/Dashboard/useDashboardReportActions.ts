import dayjs from 'dayjs';

declare global {
  interface Window {
    html2canvas: any;
  }
}
import { message } from 'antd';
import {
  DepartmentWeeklyReportItem,
  ExpressItem,
  ReportItem,
  deleteDepartmentWeeklyReport,
  fetchBiddingExpressPreviewHtml,
  fetchDepartmentWeeklyReportDetail,
  fetchExpressDetail,
  fetchReportDetail,
  generateBiddingExpress,
  generateExpress,
  generateReport,
  getApiErrorMessage,
  pushBiddingExpress,
  pushExpress,
  pushReport,
  uploadDepartmentWeeklyReport,
} from '@/services/api';
import { getWeekMonday, sanitizeHtmlForPreview } from './dashboardShared';

type DashboardReportActionContext = Record<string, any>;

export function useDashboardReportActions(ctx: DashboardReportActionContext) {
  const {
    departmentWeeklyDepartment,
    departmentWeeklyWeek,
    departmentWeeklyTitle,
    setDepartmentWeeklyUploading,
    loadDepartmentWeeklyReports,
    setDepartmentWeeklyTitle,
    setDepartmentWeeklyPreviewVisible,
    setDepartmentWeeklyPreview,
    setDepartmentWeeklyPreviewLoading,
    setNoteDialogType,
    setNoteText,
    setSelectedDate,
    setNoteDialogVisible,
    setGenerating,
    noteDialogType,
    selectedDate,
    noteText,
    loadReports,
    setPreviewVisible,
    setPreviewDetail,
    setPreviewLoading,
    previewDetail,
    setPushingReportId,
    setPushingExpressId,
    loadExpressList,
    setGeneratingExpress,
    biddingPeriod,
    setGeneratingBidding,
    setBiddingExpress,
    setPushingBidding,
  } = ctx;

  const handleUploadDepartmentWeekly = async (file: File) => {
    const department = departmentWeeklyDepartment.trim();
    if (!department) {
      message.warning('请先填写部门名称');
      return false;
    }
    if (!file.name.toLowerCase().endsWith('.html') && !file.name.toLowerCase().endsWith('.htm')) {
      message.warning('仅支持上传 HTML/HTM 周报文件');
      return false;
    }
    setDepartmentWeeklyUploading(true);
    try {
      await uploadDepartmentWeeklyReport({
        department,
        week_start: getWeekMonday(departmentWeeklyWeek).format('YYYY-MM-DD'),
        title: departmentWeeklyTitle.trim() || undefined,
        file,
      });
      message.success('部门周报已归档');
      setDepartmentWeeklyTitle('');
      await loadDepartmentWeeklyReports();
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '部门周报上传失败'));
    } finally {
      setDepartmentWeeklyUploading(false);
    }
    return false;
  };

  const handlePreviewDepartmentWeekly = async (id: number) => {
    setDepartmentWeeklyPreviewVisible(true);
    setDepartmentWeeklyPreview(null);
    setDepartmentWeeklyPreviewLoading(true);
    try {
      const detail = await fetchDepartmentWeeklyReportDetail(id);
      setDepartmentWeeklyPreview(detail);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载部门周报失败'));
    } finally {
      setDepartmentWeeklyPreviewLoading(false);
    }
  };

  const handleDeleteDepartmentWeekly = async (id: number) => {
    try {
      await deleteDepartmentWeeklyReport(id);
      message.success('部门周报已删除');
      await loadDepartmentWeeklyReports();
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '删除部门周报失败'));
    }
  };

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
          message.success('已自动推送到钉钉');
        } else {
          message.warning('生成成功，但推送失败：' + pushResult.message);
        }
      }
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '生成报告失败，请稍后重试'));
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
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载报告详情失败'));
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
    window.open(window.location.origin + shareUrl, '_blank', 'noopener,noreferrer');
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

      // 在离屏容器中渲染 HTML，避免影响当前预览布局。
      const container = document.createElement('div');
      container.innerHTML = sanitizeHtmlForPreview(previewDetail.html_content);
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
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '推送失败，请检查钉钉配置'));
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
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '推送失败，请检查钉钉配置'));
    } finally {
      setPushingExpressId(null);
    }
  };

  const handlePreviewExpress = async (expressId: number) => {
    try {
      const detail = await fetchExpressDetail(expressId);
      if (!detail?.html_content) {
        message.warning('速递内容为空，请重新生成后预览');
        return;
      }
      const blobUrl = URL.createObjectURL(new Blob([detail.html_content], { type: 'text/html;charset=utf-8' }));
      window.open(blobUrl, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '加载速递详情失败'));
    }
  };


  // —— 生成今日速递 ——
  const handleGenerateExpress = async () => {
    setGeneratingExpress(true);
    try {
      await generateExpress({ date: dayjs().format('YYYY-MM-DD') });
      message.success('今日速递生成成功');
      loadExpressList();
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '生成速递失败'));
    } finally {
      setGeneratingExpress(false);
    }
  };


  const handleGenerateBidding = async () => {
    setGeneratingBidding(true);
    try {
      const resp = await generateBiddingExpress({
        date: dayjs().format('YYYY-MM-DD'),
        period: biddingPeriod,
      });
      message.success(resp.message || '标讯速递生成成功');
      setBiddingExpress(resp);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '生成标讯速递失败'));
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
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '推送失败，请检查钉钉配置'));
    } finally {
      setPushingBidding(false);
    }
  };

  const handlePreviewBidding = async () => {
    try {
      const html = await fetchBiddingExpressPreviewHtml();
      const blobUrl = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
      window.open(blobUrl, '_blank', 'noopener,noreferrer');
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (e: any) {
      message.error(getApiErrorMessage(e, '预览失败，请先生成标讯速递'));
    }
  };

  return {
    handleUploadDepartmentWeekly,
    handlePreviewDepartmentWeekly,
    handleDeleteDepartmentWeekly,
    handleGenerateClick,
    handleGenerateConfirm,
    handlePreview,
    handleCopyLink,
    handleOpenNewWindow,
    handleConvertToImage,
    handlePushReport,
    handlePushExpress,
    handlePreviewExpress,
    handleGenerateExpress,
    handleGenerateBidding,
    handlePushBidding,
    handlePreviewBidding,
  };
}
