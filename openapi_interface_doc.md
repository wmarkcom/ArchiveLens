# OpenAPI 接口文档

项目：单用户多平台博主内容监控归档系统  
版本：v1.0  
规范：OpenAPI 3.0.3

---

## 1. 接口设计说明

本接口文档面向前后端联调，覆盖 MVP 第一版的核心接口：

1. 平台连接
2. 博主管理
3. 内容归档
4. 导入任务
5. 媒体资源
6. 通知记录
7. 系统设置
8. 总览统计

接口前缀统一为：

```text
/api
```

认证方式第一版建议采用简单后台登录态，例如：

```http
Authorization: Bearer <admin_token>
```

---

## 2. OpenAPI YAML

```yaml
openapi: 3.0.3
info:
  title: 单用户多平台博主内容监控归档系统 API
  version: 1.0.0
  description: >
    用于微博、雪球博主内容监控、归档、媒体下载、通知推送和系统配置的单用户后台 API。

servers:
  - url: /api
    description: Same-origin API

security:
  - bearerAuth: []

tags:
  - name: Dashboard
    description: 总览统计
  - name: Connections
    description: 平台连接
  - name: Accounts
    description: 监控博主
  - name: Posts
    description: 内容归档
  - name: ImportJobs
    description: 导入任务
  - name: Media
    description: 媒体资源
  - name: Notifications
    description: 通知记录
  - name: Settings
    description: 系统设置

paths:
  /dashboard/summary:
    get:
      tags: [Dashboard]
      summary: 获取总览统计
      operationId: getDashboardSummary
      responses:
        "200":
          description: 总览统计
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/DashboardSummary"

  /connections:
    get:
      tags: [Connections]
      summary: 获取平台连接列表
      operationId: listConnections
      responses:
        "200":
          description: 平台连接列表
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: "#/components/schemas/PlatformConnection"

  /connections/{platform}/status:
    get:
      tags: [Connections]
      summary: 获取单个平台连接状态
      operationId: getConnectionStatus
      parameters:
        - $ref: "#/components/parameters/PlatformPath"
      responses:
        "200":
          description: 平台连接状态
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformConnection"

  /connections/{platform}/login:
    post:
      tags: [Connections]
      summary: 创建平台登录流程
      operationId: createPlatformLogin
      parameters:
        - $ref: "#/components/parameters/PlatformPath"
      responses:
        "200":
          description: 登录流程创建成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/LoginSession"

  /connections/{platform}/logout:
    post:
      tags: [Connections]
      summary: 解绑平台并清空 session
      operationId: logoutPlatform
      parameters:
        - $ref: "#/components/parameters/PlatformPath"
      responses:
        "200":
          description: 解绑成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SuccessResponse"

  /connections/{platform}/refresh:
    post:
      tags: [Connections]
      summary: 重新检测平台登录状态
      operationId: refreshConnection
      parameters:
        - $ref: "#/components/parameters/PlatformPath"
      responses:
        "200":
          description: 检测完成
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformConnection"

  /accounts:
    get:
      tags: [Accounts]
      summary: 查询监控博主列表
      operationId: listAccounts
      parameters:
        - name: platform
          in: query
          schema:
            $ref: "#/components/schemas/Platform"
        - name: keyword
          in: query
          schema:
            type: string
        - name: status
          in: query
          schema:
            type: string
            enum: [normal, disabled, failed]
        - $ref: "#/components/parameters/Page"
        - $ref: "#/components/parameters/PageSize"
      responses:
        "200":
          description: 博主列表
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/AccountPage"

    post:
      tags: [Accounts]
      summary: 新增监控博主
      operationId: createAccount
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/AccountCreateRequest"
      responses:
        "200":
          description: 创建成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformAccount"

  /accounts/{accountId}:
    get:
      tags: [Accounts]
      summary: 获取博主详情
      operationId: getAccount
      parameters:
        - $ref: "#/components/parameters/AccountId"
      responses:
        "200":
          description: 博主详情
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformAccount"

    put:
      tags: [Accounts]
      summary: 更新博主配置
      operationId: updateAccount
      parameters:
        - $ref: "#/components/parameters/AccountId"
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/AccountUpdateRequest"
      responses:
        "200":
          description: 更新成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformAccount"

    delete:
      tags: [Accounts]
      summary: 删除监控博主
      operationId: deleteAccount
      parameters:
        - $ref: "#/components/parameters/AccountId"
      responses:
        "200":
          description: 删除成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SuccessResponse"

  /accounts/{accountId}/enable:
    post:
      tags: [Accounts]
      summary: 启用监控博主
      operationId: enableAccount
      parameters:
        - $ref: "#/components/parameters/AccountId"
      responses:
        "200":
          description: 启用成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformAccount"

  /accounts/{accountId}/disable:
    post:
      tags: [Accounts]
      summary: 停用监控博主
      operationId: disableAccount
      parameters:
        - $ref: "#/components/parameters/AccountId"
      responses:
        "200":
          description: 停用成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PlatformAccount"

  /accounts/{accountId}/check-now:
    post:
      tags: [Accounts]
      summary: 立即检测博主更新
      operationId: checkAccountNow
      parameters:
        - $ref: "#/components/parameters/AccountId"
      responses:
        "200":
          description: 已投递检测任务
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/TaskAcceptedResponse"

  /accounts/{accountId}/reimport:
    post:
      tags: [Accounts]
      summary: 重新导入历史内容
      operationId: reimportAccount
      parameters:
        - $ref: "#/components/parameters/AccountId"
      requestBody:
        required: false
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/ReimportRequest"
      responses:
        "200":
          description: 已创建导入任务
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJob"

  /posts:
    get:
      tags: [Posts]
      summary: 查询内容归档列表
      operationId: listPosts
      parameters:
        - name: platform
          in: query
          schema:
            $ref: "#/components/schemas/Platform"
        - name: account_id
          in: query
          schema:
            type: integer
            format: int64
        - name: keyword
          in: query
          schema:
            type: string
        - name: status
          in: query
          schema:
            $ref: "#/components/schemas/PostStatus"
        - name: date_start
          in: query
          schema:
            type: string
            format: date-time
        - name: date_end
          in: query
          schema:
            type: string
            format: date-time
        - $ref: "#/components/parameters/Page"
        - $ref: "#/components/parameters/PageSize"
      responses:
        "200":
          description: 内容列表
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PostPage"

  /posts/{postId}:
    get:
      tags: [Posts]
      summary: 获取内容详情
      operationId: getPost
      parameters:
        - $ref: "#/components/parameters/PostId"
      responses:
        "200":
          description: 内容详情
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/PostDetail"

  /posts/{postId}/snapshots:
    get:
      tags: [Posts]
      summary: 获取内容历史版本
      operationId: listPostSnapshots
      parameters:
        - $ref: "#/components/parameters/PostId"
      responses:
        "200":
          description: 历史快照
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: "#/components/schemas/PostSnapshot"

  /posts/{postId}/media:
    get:
      tags: [Media]
      summary: 获取某条内容的媒体资源
      operationId: listPostMedia
      parameters:
        - $ref: "#/components/parameters/PostId"
      responses:
        "200":
          description: 媒体资源列表
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: "#/components/schemas/MediaAsset"

  /import-jobs:
    get:
      tags: [ImportJobs]
      summary: 查询导入任务列表
      operationId: listImportJobs
      parameters:
        - name: status
          in: query
          schema:
            $ref: "#/components/schemas/ImportJobStatus"
        - name: platform
          in: query
          schema:
            $ref: "#/components/schemas/Platform"
        - $ref: "#/components/parameters/Page"
        - $ref: "#/components/parameters/PageSize"
      responses:
        "200":
          description: 导入任务列表
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJobPage"

  /import-jobs/{jobId}:
    get:
      tags: [ImportJobs]
      summary: 获取导入任务详情
      operationId: getImportJob
      parameters:
        - $ref: "#/components/parameters/JobId"
      responses:
        "200":
          description: 导入任务详情
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJob"

  /import-jobs/{jobId}/pause:
    post:
      tags: [ImportJobs]
      summary: 暂停导入任务
      operationId: pauseImportJob
      parameters:
        - $ref: "#/components/parameters/JobId"
      responses:
        "200":
          description: 暂停成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJob"

  /import-jobs/{jobId}/resume:
    post:
      tags: [ImportJobs]
      summary: 继续导入任务
      operationId: resumeImportJob
      parameters:
        - $ref: "#/components/parameters/JobId"
      responses:
        "200":
          description: 继续成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJob"

  /import-jobs/{jobId}/cancel:
    post:
      tags: [ImportJobs]
      summary: 取消导入任务
      operationId: cancelImportJob
      parameters:
        - $ref: "#/components/parameters/JobId"
      responses:
        "200":
          description: 取消成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJob"

  /import-jobs/{jobId}/retry:
    post:
      tags: [ImportJobs]
      summary: 重试失败导入任务
      operationId: retryImportJob
      parameters:
        - $ref: "#/components/parameters/JobId"
      responses:
        "200":
          description: 重试成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ImportJob"

  /media:
    get:
      tags: [Media]
      summary: 查询媒体资源列表
      operationId: listMediaAssets
      parameters:
        - name: download_status
          in: query
          schema:
            $ref: "#/components/schemas/MediaDownloadStatus"
        - name: media_type
          in: query
          schema:
            $ref: "#/components/schemas/MediaType"
        - name: platform
          in: query
          schema:
            $ref: "#/components/schemas/Platform"
        - $ref: "#/components/parameters/Page"
        - $ref: "#/components/parameters/PageSize"
      responses:
        "200":
          description: 媒体资源列表
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/MediaAssetPage"

  /media/{assetId}:
    get:
      tags: [Media]
      summary: 获取媒体资源详情
      operationId: getMediaAsset
      parameters:
        - $ref: "#/components/parameters/AssetId"
      responses:
        "200":
          description: 媒体资源详情
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/MediaAsset"

  /media/{assetId}/retry:
    post:
      tags: [Media]
      summary: 重试下载媒体资源
      operationId: retryMediaAsset
      parameters:
        - $ref: "#/components/parameters/AssetId"
      responses:
        "200":
          description: 已投递重试任务
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/TaskAcceptedResponse"

  /notifications:
    get:
      tags: [Notifications]
      summary: 查询通知记录
      operationId: listNotifications
      parameters:
        - name: event_type
          in: query
          schema:
            $ref: "#/components/schemas/NotificationEventType"
        - name: platform
          in: query
          schema:
            $ref: "#/components/schemas/Platform"
        - name: status
          in: query
          schema:
            $ref: "#/components/schemas/NotificationStatus"
        - name: keyword
          in: query
          schema:
            type: string
        - $ref: "#/components/parameters/Page"
        - $ref: "#/components/parameters/PageSize"
      responses:
        "200":
          description: 通知记录列表
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/NotificationPage"

  /notifications/{notificationId}:
    get:
      tags: [Notifications]
      summary: 获取通知详情
      operationId: getNotification
      parameters:
        - $ref: "#/components/parameters/NotificationId"
      responses:
        "200":
          description: 通知详情
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/NotificationEvent"

  /notifications/{notificationId}/resend:
    post:
      tags: [Notifications]
      summary: 重新发送通知
      operationId: resendNotification
      parameters:
        - $ref: "#/components/parameters/NotificationId"
      responses:
        "200":
          description: 已投递重发任务
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/TaskAcceptedResponse"

  /settings:
    get:
      tags: [Settings]
      summary: 获取系统设置
      operationId: getSettings
      responses:
        "200":
          description: 系统设置
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SystemSettings"

    put:
      tags: [Settings]
      summary: 保存系统设置
      operationId: updateSettings
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/SystemSettingsUpdateRequest"
      responses:
        "200":
          description: 保存成功
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SystemSettings"

  /settings/test-notification:
    post:
      tags: [Settings]
      summary: 测试通知渠道
      operationId: testNotification
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [channel]
              properties:
                channel:
                  type: string
                  enum: [feishu, wecom]
      responses:
        "200":
          description: 测试通知已发送
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SuccessResponse"

  /settings/backup-now:
    post:
      tags: [Settings]
      summary: 立即执行数据库备份
      operationId: backupNow
      responses:
        "200":
          description: 已投递备份任务
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/TaskAcceptedResponse"

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  parameters:
    PlatformPath:
      name: platform
      in: path
      required: true
      schema:
        $ref: "#/components/schemas/Platform"

    AccountId:
      name: accountId
      in: path
      required: true
      schema:
        type: integer
        format: int64

    PostId:
      name: postId
      in: path
      required: true
      schema:
        type: integer
        format: int64

    JobId:
      name: jobId
      in: path
      required: true
      schema:
        type: integer
        format: int64

    AssetId:
      name: assetId
      in: path
      required: true
      schema:
        type: integer
        format: int64

    NotificationId:
      name: notificationId
      in: path
      required: true
      schema:
        type: integer
        format: int64

    Page:
      name: page
      in: query
      schema:
        type: integer
        default: 1
        minimum: 1

    PageSize:
      name: page_size
      in: query
      schema:
        type: integer
        default: 20
        minimum: 1
        maximum: 100

  schemas:
    Platform:
      type: string
      enum: [weibo, xueqiu]

    PlatformConnectionStatus:
      type: string
      enum: [disconnected, pending_login, connected, expired, failed]

    PlatformConnection:
      type: object
      required: [id, platform, status]
      properties:
        id:
          type: integer
          format: int64
        platform:
          $ref: "#/components/schemas/Platform"
        status:
          $ref: "#/components/schemas/PlatformConnectionStatus"
        last_login_at:
          type: string
          format: date-time
          nullable: true
        expired_at:
          type: string
          format: date-time
          nullable: true
        error_message:
          type: string
          nullable: true

    LoginSession:
      type: object
      required: [login_session_id, login_url]
      properties:
        login_session_id:
          type: string
          format: uuid
        login_url:
          type: string

    PlatformAccountStatus:
      type: string
      enum: [normal, disabled, failed]

    InitMode:
      type: string
      enum: [none, recent, all]

    PlatformAccount:
      type: object
      required:
        - id
        - platform
        - account_name
        - profile_url
        - check_interval
        - is_enabled
        - init_mode
        - status
      properties:
        id:
          type: integer
          format: int64
        platform:
          $ref: "#/components/schemas/Platform"
        account_name:
          type: string
        profile_url:
          type: string
        platform_account_id:
          type: string
          nullable: true
        check_interval:
          type: integer
        is_enabled:
          type: boolean
        init_mode:
          $ref: "#/components/schemas/InitMode"
        init_limit:
          type: integer
        status:
          $ref: "#/components/schemas/PlatformAccountStatus"
        last_checked_at:
          type: string
          format: date-time
          nullable: true
        last_post_published_at:
          type: string
          format: date-time
          nullable: true
        error_message:
          type: string
          nullable: true

    AccountCreateRequest:
      type: object
      required: [platform, profile_url, check_interval, init_mode]
      properties:
        platform:
          $ref: "#/components/schemas/Platform"
        profile_url:
          type: string
        account_name:
          type: string
        check_interval:
          type: integer
          default: 300
        init_mode:
          $ref: "#/components/schemas/InitMode"
        init_limit:
          type: integer
          default: 100

    AccountUpdateRequest:
      type: object
      properties:
        account_name:
          type: string
        check_interval:
          type: integer
        is_enabled:
          type: boolean
        init_mode:
          $ref: "#/components/schemas/InitMode"
        init_limit:
          type: integer

    ReimportRequest:
      type: object
      properties:
        mode:
          type: string
          enum: [recent, all]
          default: recent
        target_count:
          type: integer
          default: 100

    PostStatus:
      type: string
      enum: [normal, edited, deleted, hidden, failed]

    PostListItem:
      type: object
      properties:
        id:
          type: integer
          format: int64
        platform:
          $ref: "#/components/schemas/Platform"
        account_id:
          type: integer
          format: int64
        account_name:
          type: string
        platform_post_id:
          type: string
        full_text:
          type: string
        original_url:
          type: string
        published_at:
          type: string
          format: date-time
          nullable: true
        media_count:
          type: integer
        status:
          $ref: "#/components/schemas/PostStatus"
        last_collected_at:
          type: string
          format: date-time

    PostDetail:
      allOf:
        - $ref: "#/components/schemas/PostListItem"
        - type: object
          properties:
            title:
              type: string
              nullable: true
            repost_text:
              type: string
              nullable: true
            content_hash:
              type: string
            first_collected_at:
              type: string
              format: date-time
            media:
              type: array
              items:
                $ref: "#/components/schemas/MediaAsset"
            snapshots:
              type: array
              items:
                $ref: "#/components/schemas/PostSnapshot"

    PostSnapshot:
      type: object
      properties:
        id:
          type: integer
          format: int64
        post_id:
          type: integer
          format: int64
        content_hash:
          type: string
        title:
          type: string
          nullable: true
        full_text:
          type: string
          nullable: true
        repost_text:
          type: string
          nullable: true
        captured_at:
          type: string
          format: date-time

    MediaType:
      type: string
      enum: [image, video_cover]

    MediaDownloadStatus:
      type: string
      enum: [pending, downloading, success, failed]

    MediaAsset:
      type: object
      properties:
        id:
          type: integer
          format: int64
        post_id:
          type: integer
          format: int64
        media_type:
          $ref: "#/components/schemas/MediaType"
        original_url:
          type: string
        local_path:
          type: string
          nullable: true
        file_name:
          type: string
          nullable: true
        file_size:
          type: integer
          format: int64
          nullable: true
        mime_type:
          type: string
          nullable: true
        width:
          type: integer
          nullable: true
        height:
          type: integer
          nullable: true
        download_status:
          $ref: "#/components/schemas/MediaDownloadStatus"
        retry_count:
          type: integer
        error_message:
          type: string
          nullable: true
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    ImportJobStatus:
      type: string
      enum: [pending, running, completed, failed, paused, cancelled]

    ImportJob:
      type: object
      properties:
        id:
          type: integer
          format: int64
        account_id:
          type: integer
          format: int64
        account_name:
          type: string
          nullable: true
        platform:
          $ref: "#/components/schemas/Platform"
        mode:
          type: string
          enum: [recent, all]
        target_count:
          type: integer
          nullable: true
        imported_count:
          type: integer
        cursor:
          type: string
          nullable: true
        status:
          $ref: "#/components/schemas/ImportJobStatus"
        error_message:
          type: string
          nullable: true
        started_at:
          type: string
          format: date-time
          nullable: true
        finished_at:
          type: string
          format: date-time
          nullable: true
        created_at:
          type: string
          format: date-time

    NotificationEventType:
      type: string
      enum:
        - new_post
        - edited_post
        - login_expired
        - import_failed
        - media_download_failed
        - worker_error
        - system

    NotificationStatus:
      type: string
      enum: [pending, sent, failed]

    NotificationEvent:
      type: object
      properties:
        id:
          type: integer
          format: int64
        event_type:
          $ref: "#/components/schemas/NotificationEventType"
        platform:
          $ref: "#/components/schemas/Platform"
        title:
          type: string
        content:
          type: string
          nullable: true
        channel:
          type: string
          enum: [feishu, wecom]
        status:
          $ref: "#/components/schemas/NotificationStatus"
        error_message:
          type: string
          nullable: true
        sent_at:
          type: string
          format: date-time
          nullable: true
        created_at:
          type: string
          format: date-time

    SystemSettings:
      type: object
      properties:
        default_check_interval:
          type: integer
        default_init_limit:
          type: integer
        media_root:
          type: string
        image_download_enabled:
          type: boolean
        video_cover_download_enabled:
          type: boolean
        video_file_download_enabled:
          type: boolean
        feishu_webhook:
          type: string
        wecom_webhook:
          type: string
        daily_backup_enabled:
          type: boolean
        backup_keep_days:
          type: integer
        backup_time:
          type: string

    SystemSettingsUpdateRequest:
      allOf:
        - $ref: "#/components/schemas/SystemSettings"

    DashboardSummary:
      type: object
      properties:
        account_count:
          type: integer
        post_count:
          type: integer
        media_total_size:
          type: integer
          format: int64
        failed_task_count:
          type: integer
        recent_posts:
          type: array
          items:
            $ref: "#/components/schemas/PostListItem"
        health:
          type: object
          properties:
            postgres:
              type: string
              enum: [normal, warning, error]
            redis:
              type: string
              enum: [normal, warning, error]
            worker:
              type: string
              enum: [normal, warning, error]
            media_worker:
              type: string
              enum: [normal, warning, error]
            weibo_login:
              type: string
              enum: [normal, expired, error]
        recent_events:
          type: array
          items:
            $ref: "#/components/schemas/NotificationEvent"

    Pagination:
      type: object
      properties:
        page:
          type: integer
        page_size:
          type: integer
        total:
          type: integer

    AccountPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/PlatformAccount"
        pagination:
          $ref: "#/components/schemas/Pagination"

    PostPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/PostListItem"
        pagination:
          $ref: "#/components/schemas/Pagination"

    ImportJobPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/ImportJob"
        pagination:
          $ref: "#/components/schemas/Pagination"

    MediaAssetPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/MediaAsset"
        pagination:
          $ref: "#/components/schemas/Pagination"

    NotificationPage:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: "#/components/schemas/NotificationEvent"
        pagination:
          $ref: "#/components/schemas/Pagination"

    SuccessResponse:
      type: object
      properties:
        success:
          type: boolean
          example: true
        message:
          type: string
          example: ok

    TaskAcceptedResponse:
      type: object
      properties:
        accepted:
          type: boolean
          example: true
        task_id:
          type: string
          nullable: true
        message:
          type: string
```

---

## 3. 前端路由与接口对应关系

| 前端页面 | 路由 | 主要接口 |
|---|---|---|
| 总览 | `/dashboard` | `GET /dashboard/summary` |
| 平台连接 | `/connections` | `GET /connections`、`POST /connections/{platform}/login` |
| 监控博主列表 | `/accounts` | `GET /accounts` |
| 添加监控博主 | `/accounts/new` | `POST /accounts` |
| 导入任务 | `/import-jobs` | `GET /import-jobs` |
| 内容归档列表 | `/posts` | `GET /posts` |
| 内容详情 | `/posts/:id` | `GET /posts/{postId}`、`GET /posts/{postId}/snapshots` |
| 媒体资源 | `/media` | `GET /media`、`POST /media/{assetId}/retry` |
| 通知记录 | `/notifications` | `GET /notifications`、`POST /notifications/{notificationId}/resend` |
| 系统设置 | `/settings` | `GET /settings`、`PUT /settings` |

---

## 4. 统一响应约定

### 4.1 成功响应

普通详情：

```json
{
  "id": 1,
  "status": "normal"
}
```

列表分页：

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100
  }
}
```

任务投递：

```json
{
  "accepted": true,
  "task_id": "celery-task-id",
  "message": "task accepted"
}
```

---

### 4.2 错误响应

建议统一错误格式：

```json
{
  "error": {
    "code": "LOGIN_EXPIRED",
    "message": "微博登录已过期，请重新登录",
    "details": {}
  }
}
```

常见错误码：

| 错误码 | 说明 |
|---|---|
| UNAUTHORIZED | 未登录后台 |
| FORBIDDEN | 无权限 |
| NOT_FOUND | 资源不存在 |
| VALIDATION_ERROR | 参数校验失败 |
| PLATFORM_LOGIN_EXPIRED | 平台登录过期 |
| PLATFORM_REQUEST_FAILED | 平台请求失败 |
| IMPORT_JOB_FAILED | 导入任务失败 |
| MEDIA_DOWNLOAD_FAILED | 媒体下载失败 |
| NOTIFICATION_SEND_FAILED | 通知发送失败 |
| INTERNAL_ERROR | 服务内部错误 |

---

## 5. 状态字段枚举

### 5.1 平台连接状态

```text
disconnected
pending_login
connected
expired
failed
```

### 5.2 博主状态

```text
normal
disabled
failed
```

### 5.3 内容状态

```text
normal
edited
deleted
hidden
failed
```

### 5.4 导入任务状态

```text
pending
running
completed
failed
paused
cancelled
```

### 5.5 媒体下载状态

```text
pending
downloading
success
failed
```

### 5.6 通知状态

```text
pending
sent
failed
```
