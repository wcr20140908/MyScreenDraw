# 国内代码托管与更新分发可行性（2026-10-24）

## 结论

可以在国内平台建立开源镜像，改善国内用户浏览、克隆和下载源码的路径；但**只建立 Git 仓库镜像不会加快 MyScreenDraw 现有的应用内更新**。Gitee 和 GitCode 的镜像文档都只承诺同步分支、标签和提交，GitHub Release 对象、发布说明和附件不在同步范围内。要改善便携包下载和应用内更新，必须在国内平台另外创建 Release、上传同一份 Windows ZIP，并修改后续版本的更新器以识别和校验该提供商。

建议保留 GitHub 为唯一上游和最终发布记录，分两步实施：

1. 先增加国内源码镜像和人工下载入口，不改变 6.2.0 更新器。
2. 完成真实账号、公开访问、配额和审核试验后，优先试点 GitCode Release 作为国内更新源；Gitee 可作为第二下载入口。正式让更新器信任第二平台前，应增加独立于托管平台的签名更新清单或等价的公钥校验。

本报告没有注册账号、创建仓库、上传附件或测速；不声称任何平台的实际下载速度。

## 当前实现及影响

- `main.py:1640-1641` 将版本检查固定到 GitHub Release API。
- `main.py:1661-1668` 只接受 `https://github.com/wcr20140908/MyScreenDraw/releases/download/{tag}/{name}` 形式的附件 URL。即使已有国内源码镜像，现有更新器也会拒绝国内 Release URL。
- `main.py:1685-1728` 从 GitHub 风格的 Release JSON 中按频道、语义版本和固定资产名选择 ZIP。
- `main.py:1822-1862` 校验 ZIP 大小、成员数量、路径、类型、解压总量和 `MyScreenDraw.exe` 是否存在。
- `main.py:2032-2039` 校验包内 `RELEASE-MANIFEST.json` 的版本及 EXE SHA-256；`main.py:2060-2061` 在落盘后再次校验 EXE。
- `main.py:2153-2199` 下载时限制总大小、拒绝 HTTPS 降级重定向并检查 `Content-Length` 完整性。
- `main.py:14189-14225` 在归档校验、用户确认和未保存内容处理后才移交安装事务。
- `create_release.ps1:23-64` 只使用 GitHub API 创建 draft Release、上传 ZIP 与 `.sha256`，重新校验本地发布输入后再公开。

现有校验能抵御畸形 ZIP、路径穿越、归档炸弹、版本不符和安装中断等问题，但不是独立的发布者认证。更新器没有下载并核对旁边的 `.zip.sha256`，也没有校验数字签名；包内清单和 EXE 可以被控制同一 Release 账户或托管平台的攻击者一起替换。项目自己的 `docs/code-signing.md` 也明确记录了这个边界。增加第二个更新源会增加受信任的发布账户和平台，不能只把 URL 白名单从一个域名扩成两个域名。

## 平台事实

### Gitee

- 官方镜像功能支持 GitHub → Gitee 的 Pull 镜像以及自动或手动同步，但同步对象是分支、标签和提交。自动同步依赖 GitHub Webhook、账号绑定和令牌。当前帮助页仍保留“限时开放至 2022-08-31”的旧产品说明，因此 2026 年免费个人账号能否启用自动 Pull 镜像必须登录实测。若不可用，仍可用独立 Git remote、CI 或人工推送维护单向镜像。
- Release 支持发行说明和附件，公开项目可提供下载。
- 当前官方 OpenAPI 提供 latest、按标签读取、附件列表和附件下载接口。未登录读取公开仓的 latest API 和附件 GET 在本次只读检查中可用；但官方 schema 与实际 `assets` 对象结构存在漂移，客户端需要容错或再查附件接口。
- 社区版官方配额页当前列出：单仓库 500 MB、Git 单文件 50 MB、用户总仓库容量 5 GB、附件单文件 100 MB、单仓库附件总量 1 GB。当前 GitHub v6.2.0 ZIP 为 40,702,163 字节，单个包可放入 Gitee Release；长期保留二十多个同等大小的发行包会逐渐逼近 1 GB 总附件额度。
- 企业仓改为外部开源的官方流程明确包含提交审核；个人公开仓、Release 发布是否触发当前的实名认证或人工审核，公开文档没有给出足够明确的现行规则，需要账号试验。

官方资料：

- https://help.gitee.com/repository/settings/sync-between-gitee-github
- https://help.gitee.com/questions/GitHub%E4%BB%93%E5%BA%93%E5%BF%AB%E9%80%9F%E5%AF%BC%E5%85%A5Gitee%E5%8F%8A%E5%90%8C%E6%AD%A5%E6%9B%B4%E6%96%B0
- https://help.gitee.com/repository/release/create/
- https://help.gitee.com/account/usage-quota
- https://gitee.com/api/v5/swagger
- https://gitee.com/sdk/typescript-sdk-v5/raw/main/openapi-spec.json

### GitCode / AtomGit

- 官方镜像功能支持 GitHub/Gitee → GitCode 的 Pull 镜像和 GitCode → GitHub/Gitee 的 Push 镜像；同步范围是分支、标签和提交。Release 仍需单独创建和上传。
- 官方 Release 页面支持发行说明、附件列表与下载。latest API 的公开响应可区分 `source` 与 `attach`，附件对象包含固定下载 URL、大小和 `sha256:` digest；这比当前 Gitee 的响应契约更适合作为更新元数据。
- 本次对官方公开仓 `atomgit_atomcode/atomcode` 做未登录只读检查：latest API 返回 200，附件 URL 的匿名 Range GET 经签名 CDN 返回 206。不能据此推断 MyScreenDraw 上传后一定通过内容审核，也不能据此评价下载速度。
- 官方还提供按标签读取、临时下载 URL、附件下载和获取附件上传地址的 API，发布流水线可以用令牌创建 Release 和上传资产；客户端读取公开 Release 时不应嵌入发布令牌。
- 官方“用量与存储”页面只说明登录后可查看 Git 仓库、LFS、容器和项目数量等配额，没有公开当前免费账户的数值，也没有找到现行公开的 Release 单文件及总容量上限。旧配额数字不能当作 2026 年承诺，必须登录查看并做边界上传试验。
- 官方说明公开项目所有用户均可访问，但个人公开仓、Windows 二进制附件是否需要实名认证、人工审核以及审核时长，没有找到明确的现行公开规则。

官方资料：

- https://docs.gitcode.com/docs/help/home/org_project/project_manage/project_settings/repository_mirroring/
- https://docs.gitcode.com/docs/help/home/org_project/project_manage/getting_started/project_creation_and_import/
- https://docs.gitcode.com/docs/help/home/org_project/project_manage/getting_started/repository_types/
- https://docs.gitcode.com/docs/help/home/org_project/project_manage/release_management/release_operations/
- https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-releases-latest/
- https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-releases-tag/
- https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-releases-attach-files-file-name-download/
- https://docs.gitcode.com/docs/apis/get-api-v-5-repos-owner-repo-releases-tag-upload-url/
- https://docs.gitcode.com/docs/help/home/user_center/data_management/usage_and_storage/

## 方案比较

| 方案 | 能改善什么 | 对现有更新器的影响 | 风险与限制 | 判断 |
| --- | --- | --- | --- | --- |
| GitHub 主仓 + 国内源码镜像 | 国内浏览、clone、源码归档 | 无；6.2.0 仍访问 GitHub API 和附件 | Release/附件不随镜像同步；镜像延迟和账号功能需验证 | 可立即作为低风险第一步 |
| GitHub 主仓 + Gitee 独立 Release | 国内人工下载；改造后可做更新源 | 需要提供商适配、URL 白名单和更强完整性校验 | 100 MB 单附件、1 GB 单仓附件；API schema 漂移；自动镜像产品状态文档陈旧 | 可行，适合作为第二下载入口 |
| GitHub 主仓 + GitCode 独立 Release | 国内人工下载；改造后可做更新源 | 需要提供商适配；可利用 API 的大小和 SHA-256 字段 | 免费额度、二进制审核和匿名频控未公开；需账号试验 | 技术上最适合先做自动更新试点 |

## 上线前验证门槛

1. 用真实维护账号验证公开仓创建、GitHub Pull 镜像、公开页面可见性、是否要求实名和审核。
2. 在两个平台分别创建临时 Release，上传约 41 MB ZIP 与 `.sha256`，确认单文件和总额度、MIME、文件名、重定向及删除行为。
3. 从未登录、无平台 Cookie 的环境调用 latest/按标签 API，并用 GET 或 Range GET 下载附件；记录匿名频控。不要只用 HEAD 判断 GitCode 附件是否公开。
4. 发布流程应上传同一份已经验收的 ZIP，不在平台端重新打包；上传后回读大小和 SHA-256，再匿名回下载核对。
5. 更新器必须继续按语义版本和 prerelease 状态筛选，不能把平台的“latest/最后更新”直接视为最高稳定版本。
6. 在启用第二自动更新源前，增加由离线发布密钥签名、客户端内置公钥验证的更新清单；至少要让 ZIP 哈希来自独立可验证的元数据，而不是只信任包内清单或提供商返回的 digest。

## 本次环境边界

- 当前远端：`https://github.com/wcr20140908/MyScreenDraw.git`。
- GitHub latest API 在 2026-10-24 返回公开正式版 `v6.2.0`，ZIP 为 40,702,163 字节，另有 102 字节 `.sha256`。
- 本机没有安装 `gh` CLI，因此未通过 `gh` 读取或修改 GitHub；也没有建立替代工单系统。
- 工作树在调研前已经包含用户未提交改动；本次只新增本文档，没有修改生产代码、构建脚本或配置。
