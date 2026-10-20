# Issue tracker: GitHub

本项目的需求、问题和规格使用 GitHub Issues。
通过 `gh` CLI 操作；目标仓库从当前 Git remote 确认。

## 操作前检查

确认 `gh` 可调用，并使用 `gh auth status` 检查认证。
工具或认证不可用时报告具体阻碍，不擅自改用其他跟踪系统。

## 常用操作

- 创建：`gh issue create --title "..." --body "..."`
- 读取：`gh issue view <number> --json number,title,body,labels,comments`
- 列表：`gh issue list --state open --json number,title,body,labels,assignees`
- 评论：`gh issue comment <number> --body "..."`
- 添加标签：`gh issue edit <number> --add-label "..."`
- 移除标签：`gh issue edit <number> --remove-label "..."`
- 关闭：`gh issue close <number> --comment "..."`

PowerShell 中提交多行正文时，使用 UTF-8 正文文件与 `--body-file`。

## 工单发布与读取

技能要求“发布到 issue tracker”时，创建 GitHub Issue。
技能要求“读取相关 ticket”时，读取对应 Issue 及其评论。

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding operations

- Map：使用带 `wayfinder:map` 标签的 Issue 保存探索记录与决策。
- 子工单：优先使用当前工具支持的原生子 Issue；
  不可用时，在父工单维护任务列表，并在子工单注明 `Part of #<parent>`。
- 阻塞关系：优先使用原生依赖；
  不可用时，在正文注明 `Blocked by: #<number>`。
- 选择下一任务：按 Map 顺序检查开放的子工单，
  排除仍有开放阻塞项或已有负责人的工单。
- 认领：将工单分配给实际执行者。
- 完成：评论结果、关闭工单，并将结论与工单引用补回 Map。
