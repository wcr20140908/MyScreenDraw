# C08 项目与恢复文案与私有素材草案

本写集落实已批准的 [软件教学系统计划](superpowers/plans/2026-10-07-software-teaching-system.md) C08/T7。仅新增 FILE_COPY 文案、prepare_file_fixture 私有准备器、本文与六份合成项目；不修改 main.py、teaching/application.py、catalog.json、课程JSON或测试。主线程负责正式接线、事件/目标、全部运行测试和最终验收。已落盘文案/准备器/素材按主线程要求冻结，本次收尾只编辑本文并静态验证。

## 精确资源契约

[file_copy.py](../teaching/file_copy.py) 导出 FILE_COPY：62键＝共享组标题 teaching_group_files“文件与工具”1＋课程标题 teaching_c08_title 1＋四章标题4＋28步各自title/body56。每值为 zh/en/fr/es/de/ru/ko/ja 顺序的8字符串literal tuple，共496条完整纯文本；无导入、HTML或未填插值。

四章严格为 save（7）、open_guard（8）、recovery（6）、interval（7），总28步。其中11个信息步骤、17个真实操作步骤。intro/done/guard_info/inspect_info/cost_info由用户点击现有teaching_next确认；操作等待当前步骤真实业务结果，旧事件、展示、初始化、取消/失败、未收束输入或点击“下一步”不顶替成功。done只确认本章，用户另在中心换章或teaching_exit回原工作，跳过不计完成。

- save：intro → save_first → edit → save_again → save_as → reopen → done
- open_guard：intro → make_dirty → cancel_open → discard_open → make_dirty_again → save_then_open → guard_info → done
- recovery：intro → preview → restore → inspect_info → save_restored → done
- interval：intro → preset_60 → custom → custom_75 → preset_30 → cost_info → done

## 当前真实控件与判定事实

- 文件栏实际按钮是 btn_save_project（save_project“保存项目”）、btn_save_project_as（save_project_as“另存为”）、btn_open_project（open_project“打开项目”）、btn_recovery（restore_autosave“恢复自动保存”）。正文直接使用系统展示的目标，不要求额外点被屏障禁止的工具菜单。
- 保存/另存为走真实QFileDialog和原子项目写盘；名称可自定，只允许当前活动私有练习目录。首次保存无project_path，修改后保存写回同一路径，另存为要求不同路径并保留原文件，重开指刚另存的新文件。不能凭按钮、选择器确认、project_dirty标志或旧结果单独算完整成功；要核对实际文件和全部页内容。
- 打开先选择文件，再处理QMessageBox的Save/Discard/Cancel标准角色。标准角色不是新增产品按钮；显示文字由Qt当前翻译决定，不虚构独立discard i18n键。chooser取消与未保存提示取消是不同结果。
- cancel_open只认真实unsaved.decision(decision='cancel',proceeded=False)，并核对原稿、未保存修改和路径保留。
- discard_open与save_then_open均由一次原生打开事务的最终project.opened判定：前者unsaved_choice='discard'/saved_before_open=False，后者unsaved_choice='save'/saved_before_open=True；两者还必须opened_sample=True，实际路径为panel._teaching_file_open_path并真正载入其内容。不要把同一事务的unsaved.decision/project.saved拆成能满足后续步骤的独立阶段。保存后打开还需核对写盘成功、取消/失败不继续。
- 恢复使用当前私有history，不读用户恢复历史。RecoveryDialog有有效预览、page_selector、较早版本列表、restore_button和not_now_button。preview查看有效两页history的预览后用“暂不恢复”退出，returned_without_restore=True且原稿保持；restore另启事务真实恢复。只展示对话框或“预览不可用”不完成。
- 恢复后的两页替换当前文档，不是合并到原稿；apply_autosave_data使project_path=None、project_dirty=True并重置当前撤销历史，save_restored再另写合法项目，原自动保存版本保留。
- 自动保存设置目标严格为settings.autosave_preset（document_preferences.interval_combo）和settings.autosave_custom（interval_custom/QSpinBox）。预设60/30选择数据值；自定义选项currentData=-1并真实显示SpinBox，再实际设75。自定义输入范围为5至86400秒。初始化30不代替最后preset_30操作。
- 当前autosave_interval_hint说明只保存变化内容，短间隔增加快照、压缩、磁盘负担并更快消耗保留版本，建议至少30秒。成本步骤仅说明，不要求等到定时写盘、测速或证明每次定时都生成文件。

事实依据：[main.py](../main.py) 的文件、未保存保护、恢复与间隔函数；[recovery_dialog.py](../recovery_dialog.py)、[document_preferences.py](../document_preferences.py)、[persistence.py](../persistence.py) 与 [i18n.py](../i18n.py)。业务正在由主线程接线，本文不以此前源码快照代替最终运行证据。

## 四章与两份辅助合成素材

六份文件均为本写集自行生成的合法schema_version=1、kind=myscreendraw-project、metadata.synthetic_teaching=true项目；每份两页，当前第1页、WHITE白板，只有语言无关A/B页名与自绘线段/矩形或圆，没有用户数据、外部图像、URL或凭据。各素材页面/对象身份确定且互不混淆；辅助打开样例与history内容/页面ID均区别于各章初始白板。

| 素材文件 | 角色与准备要求 |
| --- | --- |
| [files.c08.save.msd](../assets/tutorials/fixtures/files.c08.save.msd) | 保存章两页初稿，prepare后project_path=None；首次保存/编辑/再保存/另存/重开由用户完成。 |
| [files.c08.open_guard.msd](../assets/tutorials/fixtures/files.c08.open_guard.msd) | 打开保护原稿；make_dirty与make_dirty_again必须实际新增内容，初始化不预造完成事件。 |
| [files.c08.recovery.msd](../assets/tutorials/fixtures/files.c08.recovery.msd) | 恢复章两页初稿；内容与下列history不同，以便辨别真正替换。 |
| [files.c08.interval.msd](../assets/tutorials/fixtures/files.c08.interval.msd) | 间隔章两页，初始30秒且SpinBox隐藏；只改本练习配置。 |
| [files-c08-open-sample.msd](../assets/tutorials/fixtures/files-c08-open-sample.msd) | 独立两页打开样例，复制到当前data/fixtures，panel._teaching_file_open_path存私有完整路径；两个打开成功步骤只能认此实际样例。 |
| [files-c08-history.msd](../assets/tutorials/fixtures/files-c08-history.msd) | 独立两页历史源，准备器转换成AUTOSAVE_KIND并原子写入当前私有autosave目录的autosave_teaching_c08_recovery.json.gz。 |

[file_fixtures.py](../teaching/file_fixtures.py) 的prepare_file_fixture(panel,loader,fixture,paths)仅接受上述四个files.c08.*。它首先验证paths.practice、context.paths==paths和context.ui_active；不匹配时在任何I/O前拒绝，其他课程fixture直接无操作返回。准备器在events.suppress作用域初始化PEN、可绘图、关闭文本/符号/设置与缩略图、清取点/选择/练习历史，重置本章私有路径/保存状态引用，不把初始化计为学习完成。

恢复准备先验证辅助源为synthetic两页项目，再在当前活动练习专用autosave目录非递归清理autosave_*.json及autosave_*.json.gz旧候选，逐个经paths.require_write_path及已解析目录边界检查后unlink，不读或删除普通用户目录。随后原子写入唯一seed并确认当前候选恰好1份，panel._teaching_file_history_path记录实际版本；不靠数量总计代替内容区别或合法性。正式测试如有其他写入者，应由主线程在时序/私有隔离上保证“仅一份”条件。

所有素材坐标属于合成练习画布，不能通过实屏/截图/桌面捕获生成；源码准备器只供主线程活跃私有练习调用，本写集未运行它或启动应用。项目文件名、A/B/path等是角色/样例或实际路径，不作为用户精确答题字符串。文件选择器始终限制当前私有目录。

## 实际八语言控件标签

seconds_value按60秒示例展开；正文75/30按各步固定业务值，不留下运行时占位符。Qt标准未保存按钮按Save/Discard/Cancel角色核对。

| i18n键 | zh | en | fr | es | de | ru | ko | ja |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| teaching_next | 下一步 | Next step | Étape suivante | Paso siguiente | Nächster Schritt | Следующий шаг | 다음 단계 | 次の手順 |
| teaching_exit | 退出教学 | Exit tutorial | Quitter le tutoriel | Salir del tutorial | Tutorial beenden | Выйти из обучения | 튜토리얼 종료 | チュートリアルを終了 |
| save_project | 保存项目 | Save project | Enregistrer le projet | Guardar proyecto | Projekt speichern | Сохранить проект | 프로젝트 저장 | プロジェクトを保存 |
| save_project_as | 另存为 | Save As | Enregistrer sous | Guardar como | Speichern unter | Сохранить как | 다른 이름으로 저장 | 名前を付けて保存 |
| open_project | 打开项目 | Open project | Ouvrir un projet | Abrir proyecto | Projekt öffnen | Открыть проект | 프로젝트 열기 | プロジェクトを開く |
| restore_autosave | 恢复自动保存 | Restore autosave | Restaurer la sauvegarde auto | Restaurar autoguardado | Autosave wiederherstellen | Восстановить автосохранение | 자동 저장 복원 | 自動保存を復元 |
| recovery_restore | 恢复 | Restore | Restaurer | Recuperar | Wiederherstellen | Восстановить | 복구 | 復元 |
| recovery_not_now | 暂不恢复 | Not now | Pas maintenant | Ahora no | Nicht jetzt | Не сейчас | 나중에 | 今は復元しない |
| recovery_advanced | 高级选项：较早版本 | Advanced: older versions | Options avancées : anciennes versions | Avanzado: versiones anteriores | Erweitert: ältere Versionen | Дополнительно: ранние версии | 고급: 이전 버전 | 詳細：以前のバージョン |
| autosave_interval | 自动保存间隔 | Autosave interval | Intervalle de sauvegarde | Intervalo de guardado | Autospeicherintervall | Интервал автосохранения | 자동 저장 간격 | 自動保存の間隔 |
| custom_interval | 自定义… | Custom… | Personnalisé… | Personalizado… | Benutzerdefiniert… | Другое… | 사용자 지정… | カスタム… |
| seconds_value | 60 秒 | 60 seconds | 60 secondes | 60 segundos | 60 Sekunden | 60 секунд | 60초 | 60秒 |
| seconds_suffix |  秒 |  s |  s |  s |  s |  с | 초 | 秒 |

## 28步中文全文与成功条件

### save｜保存、另存为与重开

#### save.intro｜开始保存练习

**类型：** 信息

**资源键前缀：** teaching_c08_save_intro（_title / _body）

**正文：**

本章在至少两页的私有合成白板中练习首次保存、修改后再保存、另存为和重开。初始尚未指定项目文件。所有文件只放在当前独立练习目录，原工作不变。点击“下一步”开始。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 初始 files.c08.save 至少两页、PEN可绘图、设置隐藏，project_path=None，私有历史初始化不计完成。

#### save.save_first｜首次保存私有项目

**类型：** 操作

**资源键前缀：** teaching_c08_save_save_first（_title / _body）

**正文：**

点击系统展示的“保存项目”，在文件选择器中为项目命名并确认。只能保存到当前私有练习目录；名称可自定，实际写入完整项目成功后才完成，取消或只填名称不算。

**实际目标/函数：**

file.save→btn_save_project→save_project_from_file_panel→save_project

**精确成功条件与不完成反例：**

project_path 初始None；用户经真实保存选择器选当前私有根内新项目路径并确认，原子写入合法PROJECT_KIND成功，文件含全部至少两页，project_path与_teaching_last_saved_project指向本次新文件，project_dirty=False且保存签名匹配当前文档。记录实际路径A；文件名不是答案。取消、写入失败、只点保存或外部目录不完成。

#### save.edit｜在当前页增加一笔

**类型：** 操作

**资源键前缀：** teaching_c08_save_edit（_title / _body）

**正文：**

用已选中的普通笔在当前页空白处画一笔并抬起，让文档实际产生未保存修改。仅点击、预览、没有新增内容或未抬起不算；不用另点工具。

**实际目标/函数：**

canvas.ink；PEN有效新笔→释放提交

**精确成功条件与不完成反例：**

此前首次保存A成功，当前页与项目路径A保留。 用户真实绘出有长度的新笔并释放，当前页面内容/文档签名改变，has_unsaved_changes()为True；记录实际新增笔迹与当前页。初始化脏标志、无效点击、未释放、旧笔迹或无内容变化不完成。

#### save.save_again｜把修改保存回原项目

**类型：** 操作

**资源键前缀：** teaching_c08_save_save_again（_title / _body）

**正文：**

点击“保存项目”，把刚才新增的修改保存回当前项目文件。必须真实写入并解除未保存状态；不需要另选文件名，同一次旧保存不能代替这次保存。

**实际目标/函数：**

file.save→save_project

**精确成功条件与不完成反例：**

本步前A项目真实有edit新修改；用户单次真实保存写回同一路径A，磁盘项目包含该新增笔迹及全部页，project_dirty=False、保存签名与当前一致。仅同值/旧成功、取消、失败、保存到其它路径或未保存新增笔迹不完成。

#### save.save_as｜另存为第二份项目

**类型：** 操作

**资源键前缀：** teaching_c08_save_save_as（_title / _body）

**正文：**

点击“另存为”，在当前私有练习目录选一个不同名称并确认。实际写入第二份完整项目后完成，原文件仍保留；选择原路径或取消不算。

**实际目标/函数：**

file.save_as→btn_save_project_as→save_project_as

**精确成功条件与不完成反例：**

用户真实另存为选择当前私有目录内不同路径B≠A并确认，一次project.saved(action=save_as,path_changed=True)成功；B文件合法并包含当前完整至少两页与修改，A仍存在且原保存内容保留，当前project_path/last_saved=B。不以同一路径、仅选择器、失败或旧保存代替。

#### save.reopen｜重开刚另存的新项目

**类型：** 操作

**资源键前缀：** teaching_c08_save_reopen（_title / _body）

**正文：**

点击“打开项目”，只从当前私有目录选择刚刚另存的新文件。它必须真正载入，页面和已保存内容保持；只选文件、取消或打开其他文件不算。

**实际目标/函数：**

file.open→open_project_from_file_panel→open_project

**精确成功条件与不完成反例：**

选择仅当前私有目录的B；一次真实project.opened成功且reopened_saved=True，当前路径B、完整至少两页/实际内容/页面身份与B的保存payload一致。重开前无新修改，不强制额外未保存提示。A/其它文件、仅chooser、取消、失败、旧opened或未载入不完成。

#### save.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c08_save_done（_title / _body）

**正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认完成后，用户再点击本步 teaching_next，仅确认本章；不自动换章或退出，用户另在中心换章或 teaching_exit 返回原工作，跳过不计完成。

### open_guard｜打开项目时保护未保存修改

#### open_guard.intro｜开始未保存保护练习

**类型：** 信息

**资源键前缀：** teaching_c08_open_guard_intro（_title / _body）

**正文：**

本章使用至少两页私有原稿和另一份私有打开样例。你将新增修改，分别练习取消、丢弃后打开和保存后打开。先选本章私有文件，再处理未保存提示；不打开用户文件。点击“下一步”。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 初始至少两页私有原稿与复制到data/fixtures的独立合法样例，panel._teaching_file_open_path记录其私有路径；PEN可绘图，干净初始状态不代替用户make_dirty。

#### open_guard.make_dirty｜在当前页增加一笔

**类型：** 操作

**资源键前缀：** teaching_c08_open_guard_make_dirty（_title / _body）

**正文：**

用已选中的普通笔在当前页空白处画一笔并抬起，让文档实际产生未保存修改。仅点击、预览、没有新增内容或未抬起不算；不用另点工具。

**实际目标/函数：**

canvas.ink；PEN有效新笔→释放提交

**精确成功条件与不完成反例：**

本章初始原稿身份/页数保留，新增修改使它真实变脏。 用户真实绘出有长度的新笔并释放，当前页面内容/文档签名改变，has_unsaved_changes()为True；记录实际新增笔迹与当前页。初始化脏标志、无效点击、未释放、旧笔迹或无内容变化不完成。

#### open_guard.cancel_open｜取消未保存提示，保留原稿

**类型：** 操作

**资源键前缀：** teaching_c08_open_guard_cancel_open（_title / _body）

**正文：**

点击“打开项目”，在当前私有目录选本章打开样例并确认选择。出现未保存提示后选择取消。原稿和刚新增的修改必须完整保留，样例不能载入；仅取消文件选择器不算这一选择练习。

**实际目标/函数：**

file.open＋QFileDialog＋QMessageBox.StandardButton.Cancel

**精确成功条件与不完成反例：**

先真实选择本章私有打开样例，当前原稿确有make_dirty修改；用户在未保存提示选择Cancel，单次unsaved.decision(decision=cancel,proceeded=False,outcome=success)完成。对话框清理后原稿完整页面/ID/新增笔迹/路径与未保存状态保留，目标未载入。不把chooser取消、关闭教学、预置选择或取消后的project.opened旧事件计为本步。

#### open_guard.discard_open｜丢弃未保存修改并真正打开

**类型：** 操作

**资源键前缀：** teaching_c08_open_guard_discard_open（_title / _body）

**正文：**

再次点击“打开项目”，先选同一私有样例，再在未保存提示选择丢弃修改继续打开。只有样例实际载入后才完成；原稿的未保存更改不会自动保存，点丢弃按钮本身不算。

**实际目标/函数：**

file.open＋文件选择器＋QMessageBox.StandardButton.Discard→载入

**精确成功条件与不完成反例：**

当前仍是cancel_open保留的脏原稿；用户先选本章私有样例，再选Discard。只按该原生打开事务的一次project.opened(outcome=success,unsaved_choice=discard,saved_before_open=False)完成；真实模型已载入目标payload、至少两页、目标路径/页面ID/内容匹配，原脏稿被替换且不由此自动保存。不做unsaved.decision→project.opened两个独立阶段以让同一事务冒充后续事件；仅点Discard、取消/失败、旧opened或加载错误样例不完成。 正式project.opened还必须opened_sample=True，实际载入路径严格为panel._teaching_file_open_path，不接受任意私有文件。

#### open_guard.make_dirty_again｜在当前页增加一笔

**类型：** 操作

**资源键前缀：** teaching_c08_open_guard_make_dirty_again（_title / _body）

**正文：**

用已选中的普通笔在当前页空白处画一笔并抬起，让文档实际产生未保存修改。仅点击、预览、没有新增内容或未抬起不算；不用另点工具。

**实际目标/函数：**

canvas.ink；PEN有效新笔→释放提交

**精确成功条件与不完成反例：**

此前discard_open已实际载入私有样例；在其当前页新增本步新笔，使已打开样例真实变脏，记录动作前项目路径与签名。 用户真实绘出有长度的新笔并释放，当前页面内容/文档签名改变，has_unsaved_changes()为True；记录实际新增笔迹与当前页。初始化脏标志、无效点击、未释放、旧笔迹或无内容变化不完成。

#### open_guard.save_then_open｜先保存成功，再真正打开

**类型：** 操作

**资源键前缀：** teaching_c08_open_guard_save_then_open（_title / _body）

**正文：**

点击“打开项目”，先选择本章私有样例，再在未保存提示选择先保存。当前修改必须真实保存成功，随后所选项目也必须实际载入；保存取消、失败或只点保存选项都不算。若出现保存选择器，只用当前私有目录。

**实际目标/函数：**

file.open＋私有文件选择器＋QMessageBox.StandardButton.Save（必要时保存选择器）

**精确成功条件与不完成反例：**

当前make_dirty_again新增修改仍未保存；用户先选本章私有目标，再选Save，实际保存当前全部页面/新笔到合法私有项目成功且磁盘可读，随后目标实际载入。只按本原生打开事务一次project.opened(success,unsaved_choice=save,saved_before_open=True)完成，核对实际目标路径和载入内容；同一事务的project.saved/unsaved.decision不单独冒充下一步骤。保存取消/失败、未写入、仅点击Save、打开取消/失败或旧事件不完成。 正式project.opened还必须opened_sample=True，实际载入路径严格为panel._teaching_file_open_path，不接受任意私有文件。

#### open_guard.guard_info｜理解取消、丢弃与保存的区别

**类型：** 信息

**资源键前缀：** teaching_c08_open_guard_guard_info（_title / _body）

**正文：**

取消保留当前原稿和未保存修改；丢弃会放弃这些修改并打开目标；先保存只有写入成功后才继续打开，取消或失败不会算保存成功。文件选择器取消也不同于未保存提示取消。此步只说明，读完点击“下一步”。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 只说明三种真实StandardButton角色及文件选择器取消区别，不再执行一次打开/保存或改变当前文档。

#### open_guard.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c08_open_guard_done（_title / _body）

**正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认完成后，用户再点击本步 teaching_next，仅确认本章；不自动换章或退出，用户另在中心换章或 teaching_exit 返回原工作，跳过不计完成。

### recovery｜预览并恢复私有自动保存

#### recovery.intro｜开始私有自动保存恢复练习

**类型：** 信息

**资源键前缀：** teaching_c08_recovery_intro（_title / _body）

**正文：**

本章为至少两页的私有白板准备了一份独立合成自动保存。你将先预览而不恢复，再重新打开并真正恢复，最后保存恢复结果为项目。不会读取用户历史或原工作。点击“下一步”。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 初始files.c08.recovery至少两页，合成files-c08-history.msd转换为当前活动私有autosave；仅清本会话教学history避免旧版本抢默认，记录实际seed路径/版本。 当前可恢复候选严格仅1份，history为两页且内容/页面身份与本章初始画布不同。

#### recovery.preview｜预览后暂不恢复

**类型：** 操作

**资源键前缀：** teaching_c08_recovery_preview（_title / _body）

**正文：**

点击“恢复自动保存”，查看本章私有两页样例的有效预览；可用页码查看另一页。随后点击“暂不恢复”，保留当前稿并结束预览。必须真的显示有效预览，打开窗口或“预览不可用”不算。

**实际目标/函数：**

file.recovery→open_recovery_from_file_panel→RecoveryDialog.preview/page_selector/not_now_button

**精确成功条件与不完成反例：**

用户真实打开当前私有恢复入口，指定seed自动保存数据合法且实际渲染有效预览，pages=2、version为本章seed、page为有效1/2；随后真实NotNow/Reject，不恢复，原当前页面内容/ID/路径保留，dialog收尾完成。一次recovery.previewed(success,returned_without_restore=True)完成；无需额外强制较早版本或页码操作。仅dialog展示、preview不可用、错误/用户历史、直接恢复、旧preview或渲染失败不完成。

#### recovery.restore｜真正恢复两页样例

**类型：** 操作

**资源键前缀：** teaching_c08_recovery_restore（_title / _body）

**正文：**

重新点击“恢复自动保存”，确认仍为本章私有版本，再点击“恢复”。只有样例实际替换当前文档并出现其两页内容后才完成；选择版本或点按钮本身不算。

**实际目标/函数：**

file.recovery＋RecoveryDialog.restore_button→apply_autosave_data

**精确成功条件与不完成反例：**

必须重新开始本步的恢复原生事务，用户确认本章seed版本并真实Restore/Accept；一次recovery.applied(success,version=seed,pages=2)，画布实际为历史两页内容/ID/板色/当前页，project_path=None、project_dirty=True、保存签名清空、当前页历史按现实现重置。preview首次事务不冒充restore后续事件；取消、加载/渲染错误导致无有效应用、只点按钮或错误版本不完成。

#### recovery.inspect_info｜检查恢复结果与保存边界

**类型：** 信息

**资源键前缀：** teaching_c08_recovery_inspect_info（_title / _body）

**正文：**

恢复会用所选版本替换当前文档，不是把历史页合并进原稿；本章恢复后应有两页合成内容。恢复结果尚未作为项目保存，下一步再保存。当前页撤销历史会重置，不能据此自动找回替换前原稿。确认说明后点击“下一步”。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 只检查恢复后的既有两页及未保存/历史重置事实，不要求新恢复、切页或撤销；不得自动合并、跨章恢复或将预览当写盘。

#### recovery.save_restored｜把恢复结果保存成项目

**类型：** 操作

**资源键前缀：** teaching_c08_recovery_save_restored（_title / _body）

**正文：**

点击“保存项目”，将恢复结果保存为当前私有目录中的新项目文件。两页恢复内容必须真实写入成功，原自动保存版本保留；取消或仍只显示恢复画面不算。

**实际目标/函数：**

file.save→save_project→私有保存选择器

**精确成功条件与不完成反例：**

恢复后project_path=None且真实dirty；用户选择当前私有目录内新合法项目路径（不覆盖seed自动保存）并确认；project.saved success，PROJECT_KIND磁盘payload匹配恢复后的两页内容/ID，project_dirty=False，原history仍存在。文件名非指定答案；取消、失败、外部路径、覆盖自动保存、只有恢复未写盘或旧save不完成。

#### recovery.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c08_recovery_done（_title / _body）

**正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认完成后，用户再点击本步 teaching_next，仅确认本章；不自动换章或退出，用户另在中心换章或 teaching_exit 返回原工作，跳过不计完成。

### interval｜设置自动保存间隔

#### interval.intro｜开始自动保存间隔练习

**类型：** 信息

**资源键前缀：** teaching_c08_interval_intro（_title / _body）

**正文：**

本章在至少两页的私有白板中调整练习设置，初始自动保存间隔30秒。系统会展示现有设置目标；你将选择60秒、自定义75秒，再回30秒。只改本练习，不改原工作设置。点击“下一步”。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 当前活动私有练习至少两页，准备器set_autosave_interval(30,persist=False)，combo选30且SpinBox隐藏；初始化不算preset_30操作。

#### interval.preset_60｜选择60秒预设

**类型：** 操作

**资源键前缀：** teaching_c08_interval_preset_60（_title / _body）

**正文：**

在系统展示的自动保存间隔下拉框中选择“60 秒”。必须真实选择并更新本练习的间隔；只展开列表、选中原值或仅显示文字不算。

**实际目标/函数：**

settings.autosave_preset→document_preferences.interval_combo→_interval_selected→set_autosave_interval

**精确成功条件与不完成反例：**

用户真实combo选择currentData=60，当前私有autosave_interval_seconds从30变为60、timer.interval=60000（若计时器存在），私有配置保存/同步完成，SpinBox隐藏；settings.autosave_changed(success,seconds=60)完成。同值、初始化、只开列表/label、错误秒数、原工作配置或旧结果不完成。

#### interval.custom｜显示自定义秒数输入框

**类型：** 操作

**资源键前缀：** teaching_c08_interval_custom（_title / _body）

**正文：**

在同一下拉框选择“自定义…”，让现有自定义秒数输入框真实显示出来。本步只要求选择自定义并显示输入框，不要把显示框当作已经设置75秒。

**实际目标/函数：**

settings.autosave_preset→interval_combo(currentData=-1)→_interval_selected

**精确成功条件与不完成反例：**

此前60秒预设且SpinBox隐藏；用户真实选择custom_interval，combo.currentData=-1、interval_custom从隐藏到真实显示，settings.autosave_custom_opened(success,custom=True)。自动展示、只开下拉/选其它值、仍隐藏或旧opened不完成；此步不以秒数已变75代替。

#### interval.custom_75｜把自定义间隔设为75秒

**类型：** 操作

**资源键前缀：** teaching_c08_interval_custom_75（_title / _body）

**正文：**

在已显示的自定义秒数输入框中实际设置75。必须使本练习的间隔变为75秒；仅在下拉框选择自定义、输入未提交或同值空操作不算。

**实际目标/函数：**

settings.autosave_custom→document_preferences.interval_custom(QSpinBox)→_custom_changed

**精确成功条件与不完成反例：**

combo仍为自定义且SpinBox可见；用户真实使value从此前值变75，autosave_interval_seconds=75，timer75000（若有），私有配置保存并有settings.autosave_changed(success,seconds=75)。只显示custom、未提交文字、同值、setter初始化、错误数值或原工作配置不完成。

#### interval.preset_30｜选择30秒预设

**类型：** 操作

**资源键前缀：** teaching_c08_interval_preset_30（_title / _body）

**正文：**

在系统展示的自动保存间隔下拉框中选择“30 秒”。必须真实选择并更新本练习的间隔；只展开列表、选中原值或仅显示文字不算。

**实际目标/函数：**

settings.autosave_preset→document_preferences.interval_combo→_interval_selected→set_autosave_interval

**精确成功条件与不完成反例：**

用户真实combo选择currentData=30，当前私有autosave_interval_seconds从75变为30、timer.interval=30000（若计时器存在），私有配置保存/同步完成，SpinBox隐藏；settings.autosave_changed(success,seconds=30)完成。同值、初始化、只开列表/label、错误秒数、原工作配置或旧结果不完成。

#### interval.cost_info｜理解间隔过短的成本

**类型：** 信息

**资源键前缀：** teaching_c08_interval_cost_info（_title / _body）

**正文：**

自动保存仅在内容有变化时保存。间隔过短会增加快照、压缩和磁盘写入负担，也更快消耗保留版本数量；现有提示建议至少30秒。设置间隔不保证每次定时都产生新文件，也不替代手动保存项目。此步不要求等待保存或测速，读完点击“下一步”。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤读完后点击现有 teaching_next 明确确认；初始化、业务结果、自动推进或跳过不替代阅读确认。 仅说明现有autosave_interval_hint与auto_save变更签名/非空内容判断，不要求真实定时写盘、压力测试或跨原工作写配置。

#### interval.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c08_interval_done（_title / _body）

**正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**实际目标/函数：**

teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认完成后，用户再点击本步 teaching_next，仅确认本章；不自动换章或退出，用户另在中心换章或 teaching_exit 返回原工作，跳过不计完成。

## 主线程接入与验收责任

主线程负责group标题和FILE_COPY接入、28步正式课程JSON、目标解析与屏障、真实选择器/未保存提示/恢复/设置事件、私有会话清理、打包及全部测试。需绑定本步骤/epoch/原生事务，不让旧回调、尾部异常、自动初始化或同事务额外结果完成后续阶段。不要以现有测试数量单独宣称所有文案合同已验收。

保存与打开必须核对磁盘合法payload和实际画布来源，不能只看布尔标志；保存后打开若目标与当前文件同路径，应以最终读取/加载的正确版本核对，不把“写盘成功”与“载入保存后版本”混为一个未核对事实。恢复需唯一合成候选、有效预览返回不恢复、另次实际恢复两页及保存恢复项目；设置需真实combo/SpinBox交互、私有配置和秒数同步。

本次只生成文案与素材草案；源事件、目标、资源注册和应用/离屏/进程/最终运行验收由主线程负责。本写集不运行应用测试、不实屏、不读取真实data或凭据、不再委派。冻结的file_copy.py、file_fixtures.py和六素材收尾后不由本代理修改；如静态验证发现问题，先报告，由主线程当前测试收束后处理。

## 静态自查

使用AST与文本比对验证FILE_COPY为62个唯一键、每值8个完整静态字符串，共496条，严格四章7/8/6/7共28步；无导入、HTML或未填插值。11个信息步骤使用现有八语言teaching_next，四个done同时使用teaching_exit。中文28步标题/正文/条件与资源一致，正式opened_sample与单事务结果契约已记录。

prepare模块只作AST语法与限定路径/守卫审阅；六份JSON由纯数据persistence规范化检查合法PROJECT_KIND、两页、synthetic_teaching标记及内容/身份差异。本次不导入main或执行QWidget/应用测试；不能把数据静态验证当作真实私有准备器与课程流程测试通过。
