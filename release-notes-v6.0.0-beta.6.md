# MyScreenDraw v6.0.0-beta.6

## 重点更新

- **鼠标模式**：主栏模式按钮统一显示为「鼠标」。鼠标模式下隐藏批注工具和白板控制，只保留鼠标、批注、设置、关闭等基础入口。
- **批注入口**：点击「批注」切回绘图模式并显示完整批注菜单，已有内容不受影响。
- **稳定版 / 预览版频道**：设置页可以选择接收正式版或预览版更新，频道选择保存到本地配置。
- **应用内更新**：更新检查读取 GitHub release 列表；确认后在应用内后台下载 ZIP，下载完成后再次确认安装，不再打开 GitHub 下载页面。
- **数据保留**：安装过程跳过 `data/`、`exports/` 以及配置、名单、日志等用户文件；便携版设置、自动保存、名单、导出和日志继续保留。
- **归档安全**：安装前拒绝缺少 `MyScreenDraw.exe` 的 ZIP，拒绝路径穿越、绝对路径、驱动器路径、符号链接、重复条目和超过大小/成员数/解压总量限制的归档。
- **白板布局**：白板控制按钮使用更紧凑的宽度，减少无用留白，同时保留最小触控尺寸。
- **设置英文**：方向按钮使用清晰的 `Vertical` / `Horizontal` 文案。

## 验证

- 安全离屏回归：710 passed，7 skipped，581 subtests passed。
- beta.6 专项回归：96 passed，1 skipped，78 subtests passed。
- 实屏验收：42/42 checks passed；未观察到 `killTimer`、`requestActivate` 或 `UpdateLayeredWindow` 相关 Qt 警告。
- 冻结版 `--smoke-ui` 通过；exe SHA-256：`4ffc2909e8a8fe2a0159f2aa0666227f0e9cd531abfca411adc8b45243d6e0c0`。
- 便携 ZIP：`MyScreenDraw-v6.0.0-beta.6-windows-x64.zip`；ZIP SHA-256：`FC61AC5FDA357C5565F89A4D755FF8BE6021AF1F18EE6A3DE4E96C12C89B73A3`。

## 安全说明

更新功能默认关闭，只在用户开启后手动检查。下载和安装都需要明确确认；程序不会静默执行未确认的远程内容。请只从项目的官方 release 资产更新，并保留 `data/` 与 `exports/` 的备份。
