# 设置页文字反馈可行性（只读研究）

日期：2026-10-14。**研究完成，功能未实现**。本次仅整理已有研究，不重复联网，不创建表单/服务、不外发反馈。

## 结论与仓库依据

可行。首期建议“设置 → 关于 → 意见反馈”打开预填 GitHub Issue；如要求免 GitHub 账号且应用内直接发送，需要新增自建或托管 HTTPS 接收端。

- [main.py](../main.py)：`build_settings_panel()` 的“关于”可放入口，`_make_tool_window()` 可承载文字编辑；现有 `fetch_release()` / `UpdateCheckWorker` 仅为更新联网，可参考后台执行、超时、HTTPS 和响应大小限制，反馈状态应独立。
- [Issue 流程](agents/issue-tracker.md) 使用 GitHub Issues；remote 为 `wcr20140908/MyScreenDraw`。研究时本机 `gh` 不可用，未核验线上 Issues 开关与模板。
- [README 隐私说明](../README.md#隐私与数据安全)、[SECURITY.md](../SECURITY.md) 承诺不上传绘图、名单或日志；`track_event()` 只写本地日志，`_json_safe()` 仅序列化、不脱敏。
- [runtime_paths.py](../runtime_paths.py) 的 `RuntimeContext` 在教学练习中禁用更新等副作用；未来反馈入口也需阻止练习模式真实外发。文案遵循 [多语言/依赖约束](../CONTRIBUTING.md)。

## 三种可行方案

工作量为架构判断，不是工期或报价；当前三者均未接入。

| 方案 | 登录与应用内提交 | 集中查看、公开性 | 维护、费用、垃圾反馈与工作量 |
| --- | --- | --- | --- |
| 预填 GitHub Issue＋系统浏览器 | 用户需 GitHub 登录；软件可编辑，最终浏览器提交 | 直接进入现有 Issues；公开仓库普通 Issue 按公开反馈处理 | 无需新增服务器；账号门槛、重复/垃圾反馈仍需人工处理；**小** |
| 托管网页表单，如 Microsoft Forms | 配成 Anyone can respond 可免填写者登录；浏览器提交 | 作者查看响应、导出 Excel；不要公开结果链接，第三方处理数据 | 无需自运维；账户/套餐存在配额，匿名入口仍需筛选垃圾；**小至中** |
| 自建 HTTPS API＋私有反馈箱 | 可免账号、应用内异步 POST；联系方式选填 | 开发者审核、脱敏后再转 Issue，不自动公开全部匿名输入 | 部署/存储/备份/访问控制、限流/去重与持续维护；费用依选型；**客户端中等、全链路较大** |

## 必须保留的边界

- **客户端不能携带开发者 GitHub 写权限 token、App 私钥或共享可复用写凭据。** REST 创建 Issue 的细粒度令牌需要 Issues 写权限。服务器代建时，凭证仅留服务器并限制权限；客户端固定 API key 不能作为可靠防垃圾措施。
- GitHub URL 支持标题/正文预填，但过长可能返回 414；提供复制正文后打开页面的退路。Qt `QDesktopServices.openUrl()` 成功只表示已向系统交接，不能显示“反馈提交成功”。
- 自建接口仅在服务器确认保存后显示回执；超时保留文本，使用幂等请求标识避免重复。不要逆向托管表单的网页提交接口来承诺原生直发。
- 只提交用户审阅的文字与明确选择的版本/系统信息；不自动附加日志、名单、画布或机器标识，不把正文/联系方式/带正文 URL 写入日志。私有收件箱不等于匿名，服务器仍可能看到 IP；敏感问题不走公开 Issue。
- 反馈由主动提交触发，与自动更新开关分开；离线允许编辑/复制，不静默补发。上线前说明接收方、数据范围、公开性及保存方式，并补充隐私文档。

## 建议分期

1. 小范围加入浏览器 Issue 入口、预填模板与复制退路，继续使用现有 GitHub 跟踪流程。
2. 若目标用户缺少 GitHub 账号，可选托管表单作为收集入口，开发者审核后归档到 Issue。
3. 只有明确需要免登录、应用内直发时，再建设受控 HTTPS 接收端及回执/防垃圾机制。

本记录不授权实现上述任何阶段；6.2.0 当前仍不包含文字反馈功能。

## 已核验的官方资料

本次只读研究核验的官方资料如下；收尾时再次核对了 GitHub URL 预填、凭证保护及 Microsoft Forms 的免登录收集和结果查看说明：

- GitHub：[URL 预填与长度限制](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query)、[用户账号](https://docs.github.com/en/get-started/learning-about-github/types-of-github-accounts)。
- GitHub：[创建 Issue 的 REST 权限](https://docs.github.com/en/rest/issues/issues#create-an-issue)、[认证凭证保护](https://docs.github.com/en/rest/authentication/keeping-your-api-credentials-secure)。
- Microsoft Forms：[免登录收集选项](https://support.microsoft.com/en-us/forms/send-a-form-and-collect-responses)、[响应与结果分享](https://support.microsoft.com/en-us/office/check-and-share-your-form-results-02859424-341d-406f-b32a-9a0fbaf357af)、[账户配额](https://support.microsoft.com/en-us/forms/form-question-response-and-character-limits-in-microsoft-forms)。
- Qt：[QDesktopServices.openUrl 的成功语义](https://doc.qt.io/qt-6/qdesktopservices.html#openUrl)。
