import { createRouter, createWebHistory } from 'vue-router'

import AccountFormView from './views/AccountFormView.vue'
import AccountsView from './views/AccountsView.vue'
import ConnectionsView from './views/ConnectionsView.vue'
import DashboardView from './views/DashboardView.vue'
import ImportJobsView from './views/ImportJobsView.vue'
import MediaView from './views/MediaView.vue'
import NotificationsView from './views/NotificationsView.vue'
import PlatformLoginView from './views/PlatformLoginView.vue'
import PostDetailView from './views/PostDetailView.vue'
import PostsView from './views/PostsView.vue'
import SettingsView from './views/SettingsView.vue'
import WorkerLogsView from './views/WorkerLogsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    {
      path: '/dashboard',
      component: DashboardView,
      meta: { title: '总览', subtitle: '查看监控运行状态、归档数量、媒体占用和最近事件' },
    },
    {
      path: '/connections',
      component: ConnectionsView,
      meta: { title: '平台连接', subtitle: '管理微博、雪球授权登录态和重新登录入口' },
    },
    {
      path: '/platform-login/:platform/:sessionId',
      component: PlatformLoginView,
      meta: { title: '扫码登录', subtitle: '复制链接到浏览器，完成扫码并保存服务器登录态' },
    },
    {
      path: '/accounts',
      component: AccountsView,
      meta: { title: '监控博主', subtitle: '管理需要定时采集和归档的微博、雪球博主' },
    },
    {
      path: '/accounts/new',
      component: AccountFormView,
      meta: { title: '添加监控博主', subtitle: '配置主页链接、检查频率和初始化导入策略' },
    },
    {
      path: '/accounts/:id/edit',
      component: AccountFormView,
      meta: { title: '编辑监控博主', subtitle: '修改主页链接、检查频率和初始化导入策略' },
    },
    {
      path: '/import-jobs',
      component: ImportJobsView,
      meta: { title: '导入任务', subtitle: '查看历史内容导入进度、失败原因和重试状态' },
    },
    {
      path: '/posts',
      component: PostsView,
      meta: { title: '内容归档', subtitle: '搜索、筛选和查看已归档的正文、图片、视频封面' },
    },
    {
      path: '/posts/:id',
      component: PostDetailView,
      meta: { title: '内容详情', subtitle: '查看正文、媒体资源、原文链接和历史快照' },
    },
    {
      path: '/media',
      component: MediaView,
      meta: { title: '媒体资源', subtitle: '查看本地图片和视频封面下载状态' },
    },
    {
      path: '/notifications',
      component: NotificationsView,
      meta: { title: '通知记录', subtitle: '查看新内容、编辑、登录过期和任务异常通知' },
    },
    {
      path: '/worker-logs',
      component: WorkerLogsView,
      meta: { title: '运行日志', subtitle: '查看 Worker 定时扫描、采集、导入和媒体下载的执行记录' },
    },
    {
      path: '/settings',
      component: SettingsView,
      meta: { title: '系统设置', subtitle: '配置采集频率、媒体归档、推送渠道、安全和备份策略' },
    },
  ],
})

export default router
