# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup locale selection and the complete UI string table.

设计约定
--------
1. **界面上出现的每一个字符串都必须在这里登记**，代码里不允许硬编码文案。
   界面文案的 key 完整性与 8 语言齐全性由 `tests/test_i18n_and_telemetry.py` 保证
   （各语言 key 集合一致、值非空）；「所有面向用户的字符串走 tr()」这一约定
   由代码审查保证（Qt 内建对话框按钮等系统文案由 Qt 自身翻译）。
2. `_BASE` 的每个值是一个 8 元组，顺序固定为 `_LANGS`：
   zh, en, fr, es, de, ru, ko, ja。
   模块导入时会校验长度，写少一项就会立刻抛错，而不是在界面上显示成 key。
3. 带占位符的文案用 `trf(key, **kwargs)` 取用，内部是 `str.format`，
   缺参数时回退到原始模板而不是崩溃——课堂上宁可显示得难看，也不能弹异常。
"""
from __future__ import annotations

from PyQt6.QtCore import QLocale

_LANGS = ("zh", "en", "fr", "es", "de", "ru", "ko", "ja")

SUPPORTED = {
    QLocale.Language.Chinese: "zh",
    QLocale.Language.English: "en",
    QLocale.Language.French: "fr",
    QLocale.Language.Spanish: "es",
    QLocale.Language.German: "de",
    QLocale.Language.Russian: "ru",
    QLocale.Language.Korean: "ko",
    QLocale.Language.Japanese: "ja",
}

# 顺序：zh, en, fr, es, de, ru, ko, ja
_BASE = {
    # ---------- 应用与主工具栏 ----------
    "app": ("教学批注", "Screen Annotation", "Annotation", "Anotación", "Bildschirmannotation", "Аннотация", "화면 주석", "画面注釈"),
    "pen": ("普通笔", "Pen", "Stylo", "Pluma", "Stift", "Перо", "펜", "ペン"),
    "marker": ("荧光笔", "Highlighter", "Surligneur", "Resaltador", "Textmarker", "Маркер", "형광펜", "蛍光ペン"),
    "laser": ("激光笔", "Laser", "Laser", "Láser", "Laser", "Лазер", "레이저", "レーザー"),
    "eraser": ("橡皮", "Eraser", "Gomme", "Borrador", "Radierer", "Ластик", "지우개", "消しゴム"),
    "select": ("框选", "Select", "Sélection", "Seleccionar", "Auswählen", "Выбор", "선택", "選択"),
    "text": ("文本框", "Text", "Texte", "Texto", "Text", "Текст", "텍스트", "テキスト"),
    "shape": ("图形", "Shapes", "Formes", "Formas", "Formen", "Фигуры", "도형", "図形"),
    "tools": ("工具", "Tools", "Outils", "Herramientas", "Werkzeuge", "Инструменты", "도구", "ツール"),
    "undo": ("撤销", "Undo", "Annuler", "Deshacer", "Rückgängig", "Отменить", "실행 취소", "元に戻す"),
    "redo": ("重做", "Redo", "Rétablir", "Rehacer", "Wiederholen", "Повторить", "다시 실행", "やり直す"),
    "clear": ("清屏", "Clear", "Effacer", "Borrar", "Löschen", "Очистить", "지우기", "クリア"),
    "annotate": ("批注", "Annotate", "Annoter", "Anotar", "Annotieren", "Аннотация", "주석", "注釈"),
    "passthrough": ("穿透模式", "Click-through", "Mode transparent", "Modo transparente", "Durchklicken", "Прозрачный режим", "클릭 통과", "透過モード"),
    "drawing_mode": ("绘图模式", "Drawing Mode", "Mode dessin", "Modo dibujo", "Zeichenmodus", "Режим рисования", "그리기 모드", "描画モード"),
    "exit": ("退出软件", "Exit", "Quitter", "Salir", "Beenden", "Выход", "종료", "終了"),
    "open": ("打开", "Open", "Ouvrir", "Abrir", "Öffnen", "Открыть", "열기", "開く"),
    "save": ("保存", "Save", "Enregistrer", "Guardar", "Speichern", "Сохранить", "저장", "保存"),
    "cancel": ("取消", "Cancel", "Annuler", "Cancelar", "Abbrechen", "Отмена", "취소", "キャンセル"),
    "rotate": ("旋转", "Rotate", "Pivoter", "Girar", "Drehen", "Повернуть", "회전", "回転"),
    "portrait": ("竖版", "Portrait", "Portrait", "Retrato", "Hochformat", "Вертикаль", "세로", "縦型"),
    "landscape": ("横版", "Landscape", "Paysage", "Paisaje", "Querformat", "Горизонталь", "가로", "横型"),

    # ---------- 白板 ----------
    "whiteboard": ("进入白板", "Whiteboard", "Tableau blanc", "Pizarra", "Whiteboard", "Доска", "화이트보드", "ホワイトボード"),
    "exit_whiteboard": ("退出白板", "Exit Whiteboard", "Quitter le tableau", "Salir de pizarra", "Whiteboard beenden", "Выйти с доски", "화이트보드 종료", "ホワイトボード終了"),
    "prev": ("上页", "Previous", "Précédent", "Anterior", "Zurück", "Назад", "이전", "前へ"),
    "next": ("下页", "Next", "Suivant", "Siguiente", "Weiter", "Вперёд", "다음", "次へ"),
    "new_page": ("新页", "New Page", "Nouvelle page", "Página nueva", "Neue Seite", "Новая страница", "새 페이지", "新しいページ"),
    "board": ("黑板", "Blackboard", "Tableau noir", "Pizarra negra", "Tafel", "Чёрная доска", "칠판", "黒板"),
    "board_white": ("白板", "Whiteboard", "Tableau blanc", "Pizarra", "Whiteboard", "Белая доска", "화이트보드", "ホワイトボード"),
    "page_label": ("第 {index} 页", "Page {index}", "Page {index}", "Página {index}", "Seite {index}", "Стр. {index}", "{index} 페이지", "{index} ページ"),

    # ---------- 主题 ----------
    "theme": ("主题", "Theme", "Thème", "Tema", "Thema", "Тема", "테마", "テーマ"),
    "dark_theme": ("暗色主题", "Dark Theme", "Thème sombre", "Tema oscuro", "Dunkles Thema", "Тёмная тема", "어두운 테마", "ダークテーマ"),
    "light_theme": ("亮色主题", "Light Theme", "Thème clair", "Tema claro", "Helles Thema", "Светлая тема", "밝은 테마", "ライトテーマ"),

    # ---------- 通用参数标签 ----------
    "width": ("粗细", "Width", "Épaisseur", "Grosor", "Stärke", "Толщина", "굵기", "太さ"),
    "opacity": ("透明度", "Opacity", "Opacité", "Opacidad", "Deckkraft", "Прозрачность", "투명도", "不透明度"),
    "sensitivity": ("感应", "Sensitivity", "Sensibilité", "Sensibilidad", "Empfindlichkeit", "Чувствительность", "감도", "感度"),
    "width_value": ("粗细: {value}", "Width: {value}", "Épaisseur : {value}", "Grosor: {value}", "Stärke: {value}", "Толщина: {value}", "굵기: {value}", "太さ: {value}"),
    "opacity_value": ("透明度: {value}%", "Opacity: {value}%", "Opacité : {value} %", "Opacidad: {value}%", "Deckkraft: {value}%", "Прозрачность: {value}%", "투명도: {value}%", "不透明度: {value}%"),
    "sensitivity_value": ("感应: {value}", "Sensitivity: {value}", "Sensibilité : {value}", "Sensibilidad: {value}", "Empfindlichkeit: {value}", "Чувствительность: {value}", "감도: {value}", "感度: {value}"),

    # ---------- 批注设置 ----------
    "choose_annotate_tool": ("选择批注工具", "Choose annotation tool", "Choisir l'outil", "Elegir herramienta", "Werkzeug wählen", "Выберите инструмент", "주석 도구 선택", "注釈ツールを選択"),
    "annotate_hint": ("点选工具即可使用；再次点击当前工具可打开设置", "Tap a tool to use it; tap it again to open its settings", "Touchez un outil pour l'utiliser ; touchez à nouveau pour les réglages", "Toque una herramienta para usarla; tóquela otra vez para ajustes", "Werkzeug antippen zum Benutzen; erneut antippen für Einstellungen", "Нажмите инструмент для выбора; повторно — настройки", "도구를 눌러 사용하고, 다시 누르면 설정이 열립니다", "ツールをタップして使用、もう一度タップで設定"),
    "smart_shapes_on": ("智能识别图形：开", "Smart shapes: ON", "Formes auto : ON", "Formas auto: ON", "Formerkennung: EIN", "Распознавание фигур: ВКЛ", "도형 인식: 켜짐", "図形認識: オン"),
    "smart_shapes_off": ("智能识别图形：关", "Smart shapes: OFF", "Formes auto : OFF", "Formas auto: OFF", "Formerkennung: AUS", "Распознавание фигур: ВЫКЛ", "도형 인식: 꺼짐", "図形認識: オフ"),
    "smart_shapes_hint": ("停笔即转标准图形\n连画 3 段短线成虚线", "Hold still to snap to a shape\n3 short collinear strokes make a dashed line", "Maintenez pour convertir en forme\n3 traits alignés = ligne pointillée", "Mantenga para convertir en forma\n3 trazos alineados = línea discontinua", "Halten zum Umwandeln in Form\n3 kurze Striche = gestrichelte Linie", "Задержите для превращения в фигуру\n3 коротких штриха = пунктир", "멈추면 표준 도형으로 변환\n짧은 선 3개는 점선", "止めると図形に変換\n短い線3本で破線"),

    # ---------- 激光笔 ----------
    "laser_color": ("激光笔颜色", "Laser colour", "Couleur du laser", "Color del láser", "Laserfarbe", "Цвет лазера", "레이저 색상", "レーザーの色"),
    "laser_dot": ("光点: {value}", "Dot: {value}", "Point : {value}", "Punto: {value}", "Punkt: {value}", "Точка: {value}", "점 크기: {value}", "光点: {value}"),
    "laser_hint": ("仅指示·不落墨\n不触发智能图形", "Pointer only — leaves no ink\nnever triggers shape recognition", "Pointeur seulement — sans encre\naucune reconnaissance", "Solo puntero — sin tinta\nsin reconocimiento", "Nur Zeiger — keine Tinte\nkeine Formerkennung", "Только указатель — без чернил\nбез распознавания", "표시만 하며 잉크 없음\n도형 인식 안 함", "指示のみ・インクなし\n図形認識なし"),
    "choose_laser_color": ("选择激光笔颜色", "Choose laser colour", "Couleur du laser", "Color del láser", "Laserfarbe wählen", "Выбор цвета лазера", "레이저 색상 선택", "レーザーの色を選択"),

    # ---------- 荧光笔 ----------
    "choose_marker_color": ("选择荧光笔颜色", "Choose highlighter colour", "Couleur du surligneur", "Color del resaltador", "Textmarkerfarbe wählen", "Цвет маркера", "형광펜 색상 선택", "蛍光ペンの色を選択"),

    # ---------- 橡皮 ----------
    "eraser_circle": ("圆形擦", "Area", "Zone", "Área", "Fläche", "Область", "영역 지우개", "範囲消し"),
    "eraser_stroke": ("线条擦", "Stroke", "Trait", "Trazo", "Strich", "Штрих", "선 지우개", "線消し"),

    # ---------- 放大镜 ----------
    "magnifier": ("放大镜", "Magnifier", "Loupe", "Lupa", "Lupe", "Лупа", "확대경", "拡大鏡"),
    "zoom_value": ("倍率: {value}%", "Zoom: {value}%", "Zoom : {value} %", "Zoom: {value}%", "Zoom: {value}%", "Увеличение: {value}%", "배율: {value}%", "倍率: {value}%"),
    "zoom_step": ("每档 50%", "50% per step", "50 % par cran", "50% por paso", "50% pro Schritt", "Шаг 50%", "단계당 50%", "1段階 50%"),
    "lens_value": ("镜面: {value}", "Lens: {value}", "Lentille : {value}", "Lente: {value}", "Linse: {value}", "Линза: {value}", "렌즈: {value}", "レンズ: {value}"),
    "refresh_frame": ("刷新画面", "Refresh frame", "Rafraîchir", "Actualizar", "Aktualisieren", "Обновить кадр", "화면 새로 고침", "画面を更新"),
    "wheel_zoom_hint": ("滚轮也可缩放", "Mouse wheel also zooms", "La molette zoome aussi", "La rueda también amplía", "Mausrad zoomt ebenfalls", "Колесо тоже меняет масштаб", "휠로도 확대/축소", "ホイールでも拡大縮小"),
    "spotlight": ("聚光灯", "Spotlight", "Projecteur", "Foco", "Spotlight", "Прожектор", "집중 조명", "スポットライト"),

    # ---------- 图形工具 ----------
    "shape_line": ("直线", "Line", "Ligne", "Línea", "Linie", "Линия", "직선", "直線"),
    "shape_dashed_line": ("虚线", "Dashed line", "Pointillés", "Discontinua", "Gestrichelt", "Пунктир", "점선", "破線"),
    "shape_triangle": ("三角形", "Triangle", "Triangle", "Triángulo", "Dreieck", "Треугольник", "삼각형", "三角形"),
    "shape_rect": ("矩形", "Rectangle", "Rectangle", "Rectángulo", "Rechteck", "Прямоугольник", "직사각형", "長方形"),
    "shape_parallelogram": ("平行四边形", "Parallelogram", "Parallélogramme", "Paralelogramo", "Parallelogramm", "Параллелограмм", "평행사변형", "平行四辺形"),
    "shape_trapezoid": ("梯形", "Trapezoid", "Trapèze", "Trapecio", "Trapez", "Трапеция", "사다리꼴", "台形"),
    "shape_diamond": ("菱形", "Rhombus", "Losange", "Rombo", "Raute", "Ромб", "마름모", "ひし形"),
    "shape_angle": ("角", "Angle", "Angle", "Ángulo", "Winkel", "Угол", "각", "角"),
    "shape_circle": ("圆形+圆心", "Circle + centre", "Cercle + centre", "Círculo + centro", "Kreis + Mittelpunkt", "Круг + центр", "원 + 중심", "円 + 中心"),
    "shape_ellipse": ("椭圆形", "Ellipse", "Ellipse", "Elipse", "Ellipse", "Эллипс", "타원", "楕円"),
    "shape_cuboid": ("长方体", "Cuboid", "Pavé droit", "Prisma", "Quader", "Параллелепипед", "직육면체", "直方体"),
    "shape_cube": ("正方体", "Cube", "Cube", "Cubo", "Würfel", "Куб", "정육면체", "立方体"),
    "shape_cylinder": ("圆柱体", "Cylinder", "Cylindre", "Cilindro", "Zylinder", "Цилиндр", "원기둥", "円柱"),
    "shape_cone": ("圆锥体", "Cone", "Cône", "Cono", "Kegel", "Конус", "원뿔", "円錐"),
    "hint_drag_draw": ("拖拽绘制", "Drag to draw", "Glisser pour dessiner", "Arrastre para dibujar", "Ziehen zum Zeichnen", "Перетащите для рисования", "드래그하여 그리기", "ドラッグで描画"),
    "hint_two_endpoints": ("点 2 个端点·可吸附", "Tap 2 endpoints · snaps", "2 extrémités · magnétisme", "2 extremos · imantado", "2 Endpunkte · Einrasten", "2 конца · привязка", "끝점 2개 · 스냅", "端点2つ・スナップ"),
    "hint_three_vertices": ("点 3 个顶点", "Tap 3 vertices", "3 sommets", "3 vértices", "3 Eckpunkte", "3 вершины", "꼭짓점 3개", "頂点3つ"),
    "hint_two_corners": ("点对角 2 点", "Tap 2 opposite corners", "2 coins opposés", "2 esquinas opuestas", "2 gegenüberliegende Ecken", "2 противоположных угла", "대각 2점", "対角2点"),
    "hint_three_adjacent": ("点相邻 3 顶点", "Tap 3 adjacent vertices", "3 sommets adjacents", "3 vértices adyacentes", "3 benachbarte Ecken", "3 смежные вершины", "인접 꼭짓점 3개", "隣接する頂点3つ"),
    "hint_trapezoid": ("下底 2 点+上底 2 点", "2 base points + 2 top points", "2 points base + 2 points haut", "2 base + 2 superior", "2 Basis- + 2 Deckpunkte", "2 нижних + 2 верхних", "아랫변 2점 + 윗변 2점", "下底2点＋上底2点"),
    "hint_circle": ("圆心+圆周 1 点", "Centre + 1 point on the circle", "Centre + 1 point", "Centro + 1 punto", "Mittelpunkt + 1 Punkt", "Центр + 1 точка", "중심 + 원 위 1점", "中心＋円周1点"),
    "hint_ellipse": ("中心+外缘 1 点", "Centre + 1 edge point", "Centre + 1 point du bord", "Centro + 1 punto del borde", "Mittelpunkt + 1 Randpunkt", "Центр + 1 точка края", "중심 + 가장자리 1점", "中心＋外縁1点"),
    "hint_diamond": ("对角 2 点+侧点定宽", "2 diagonal points + 1 side point", "2 points diagonaux + 1 latéral", "2 diagonales + 1 lateral", "2 Diagonalpunkte + 1 Seitenpunkt", "2 точки диагонали + боковая", "대각 2점 + 측면 1점", "対角2点＋側点"),
    "hint_angle": ("顶点+两边端点各 1 点", "Vertex + 1 point on each arm", "Sommet + 1 point par côté", "Vértice + 1 punto por lado", "Scheitel + je 1 Punkt", "Вершина + по точке на сторонах", "꼭짓점 + 두 변에 각 1점", "頂点＋両辺に1点ずつ"),
    "cancel_points": ("取消取点", "Cancel points", "Annuler les points", "Cancelar puntos", "Punkte verwerfen", "Отменить точки", "점 취소", "点をキャンセル"),
    "shape_hint_suffix": ("{hint} · 右键或「取消取点」撤销", "{hint} · right-click or “Cancel points” to undo", "{hint} · clic droit ou « Annuler les points »", "{hint} · clic derecho o «Cancelar puntos»", "{hint} · Rechtsklick oder „Punkte verwerfen“", "{hint} · ПКМ или «Отменить точки»", "{hint} · 우클릭 또는 「점 취소」", "{hint} · 右クリックまたは「点をキャンセル」"),
    "shape_hint_default": ("点击取点 · 右键或「取消取点」撤销", "Tap to place points · right-click or “Cancel points” to undo", "Touchez pour placer · clic droit pour annuler", "Toque para colocar · clic derecho para cancelar", "Antippen zum Setzen · Rechtsklick zum Verwerfen", "Нажмите для точек · ПКМ для отмены", "탭하여 점 찍기 · 우클릭으로 취소", "タップで点を置く・右クリックで取消"),

    # ---------- 选中面板 ----------
    "selection_none": ("未选择对象", "Nothing selected", "Aucune sélection", "Nada seleccionado", "Nichts ausgewählt", "Ничего не выбрано", "선택 없음", "選択なし"),
    "selection_count": ("已选择: {count}", "Selected: {count}", "Sélectionné : {count}", "Seleccionado: {count}", "Ausgewählt: {count}", "Выбрано: {count}", "선택됨: {count}", "選択中: {count}"),
    "duplicate": ("复", "Copy", "Copie", "Copia", "Kopie", "Копия", "복사", "複製"),
    "delete": ("删", "Del", "Suppr", "Borrar", "Löschen", "Удал.", "삭제", "削除"),
    "more": ("⋯", "⋯", "⋯", "⋯", "⋯", "⋯", "⋯", "⋯"),
    "duplicate_tip": ("复制：副本贴在旁边并选中", "Duplicate: the copy lands beside it and stays selected", "Dupliquer : la copie apparaît à côté", "Duplicar: la copia queda al lado", "Duplizieren: Kopie erscheint daneben", "Дублировать: копия рядом", "복제: 복사본이 옆에 생성됨", "複製: 隣にコピーを作成"),
    "delete_tip": ("删除选中对象", "Delete the selected objects", "Supprimer la sélection", "Eliminar la selección", "Auswahl löschen", "Удалить выбранное", "선택 항목 삭제", "選択項目を削除"),
    "more_tip": ("更多几何操作（平面图形）", "More geometry operations (2-D shapes)", "Plus d'opérations (formes 2D)", "Más operaciones (formas 2D)", "Weitere Geometrie (2-D)", "Больше построений (2D)", "추가 기하 작업 (평면 도형)", "その他の作図（平面図形）"),
    "change_color": ("改色", "Colour", "Couleur", "Color", "Farbe", "Цвет", "색상", "色変更"),
    "choose_object_color": ("选择对象颜色", "Choose object colour", "Couleur de l'objet", "Color del objeto", "Objektfarbe wählen", "Цвет объекта", "개체 색상 선택", "オブジェクトの色"),
    "choose_custom_color": ("选择自定义颜色", "Choose a custom colour", "Couleur personnalisée", "Color personalizado", "Eigene Farbe wählen", "Свой цвет", "사용자 색상 선택", "カスタム色を選択"),

    # ---------- 几何构造 ----------
    "op_circumcircle": ("外接圆", "Circumcircle", "Cercle circonscrit", "Circunferencia circunscrita", "Umkreis", "Описанная окружность", "외접원", "外接円"),
    "op_incircle": ("内切圆", "Incircle", "Cercle inscrit", "Circunferencia inscrita", "Inkreis", "Вписанная окружность", "내접원", "内接円"),
    "op_medians": ("三条中线", "Medians", "Médianes", "Medianas", "Seitenhalbierende", "Медианы", "중선", "中線"),
    "op_altitudes": ("三条高", "Altitudes", "Hauteurs", "Alturas", "Höhen", "Высоты", "수선", "高さ"),
    "op_midsegment": ("中位线三角形", "Midsegment triangle", "Triangle des milieux", "Triángulo medial", "Mittendreieck", "Срединный треугольник", "중점 삼각형", "中点三角形"),
    "op_diagonals": ("对角线", "Diagonals", "Diagonales", "Diagonales", "Diagonalen", "Диагонали", "대각선", "対角線"),
    "op_center": ("中心点", "Centre point", "Centre", "Centro", "Mittelpunkt", "Центр", "중심점", "中心点"),
    "op_height": ("高", "Height", "Hauteur", "Altura", "Höhe", "Высота", "높이", "高さ"),
    "op_diameter": ("直径", "Diameter", "Diamètre", "Diámetro", "Durchmesser", "Диаметр", "지름", "直径"),
    "op_radius": ("半径", "Radius", "Rayon", "Radio", "Radius", "Радиус", "반지름", "半径"),
    "op_inscribed_square": ("内接正方形", "Inscribed square", "Carré inscrit", "Cuadrado inscrito", "Einbeschriebenes Quadrat", "Вписанный квадрат", "내접 정사각형", "内接正方形"),
    "op_circumscribed_square": ("外切正方形", "Circumscribed square", "Carré circonscrit", "Cuadrado circunscrito", "Umbeschriebenes Quadrat", "Описанный квадрат", "외접 정사각형", "外接正方形"),
    "op_inscribed_triangle": ("内接等边三角形", "Inscribed equilateral triangle", "Triangle équilatéral inscrit", "Triángulo equilátero inscrito", "Einbeschriebenes gleichseitiges Dreieck", "Вписанный равносторонний треугольник", "내접 정삼각형", "内接正三角形"),
    "op_axes": ("长轴与短轴", "Major and minor axes", "Grand et petit axes", "Ejes mayor y menor", "Haupt- und Nebenachse", "Большая и малая оси", "장축과 단축", "長軸と短軸"),
    "op_foci": ("两个焦点", "Both foci", "Les deux foyers", "Ambos focos", "Beide Brennpunkte", "Оба фокуса", "두 초점", "2つの焦点"),
    "op_midpoint": ("中点标记", "Midpoint marker", "Marque du milieu", "Marca del punto medio", "Mittelpunktmarke", "Отметка середины", "중점 표시", "中点マーク"),
    "op_perp_bisector": ("垂直平分线", "Perpendicular bisector", "Médiatrice", "Mediatriz", "Mittelsenkrechte", "Серединный перпендикуляр", "수직이등분선", "垂直二等分線"),
    "angle_current": ("当前角度：{value}°", "Current angle: {value}°", "Angle actuel : {value}°", "Ángulo actual: {value}°", "Aktueller Winkel: {value}°", "Текущий угол: {value}°", "현재 각도: {value}°", "現在の角度: {value}°"),
    "angle_plus": ("角度 +5°", "Angle +5°", "Angle +5°", "Ángulo +5°", "Winkel +5°", "Угол +5°", "각도 +5°", "角度 +5°"),
    "angle_minus": ("角度 −5°", "Angle −5°", "Angle −5°", "Ángulo −5°", "Winkel −5°", "Угол −5°", "각도 −5°", "角度 −5°"),
    "angle_preset": ("设为常用角", "Set to a common angle", "Angle courant", "Ángulo común", "Gängiger Winkel", "Типовой угол", "자주 쓰는 각도", "よく使う角度"),
    "angle_bisector": ("作角平分线", "Draw angle bisector", "Tracer la bissectrice", "Trazar bisectriz", "Winkelhalbierende zeichnen", "Построить биссектрису", "각의 이등분선", "角の二等分線"),

    # ---------- 教具 ----------
    "aids": ("辅助作图", "Drawing Aids", "Outils de dessin", "Reglas", "Zeichenhilfen", "Чертёжные инструменты", "그리기 도구", "作図ツール"),
    "aid_ruler": ("直尺", "Ruler", "Règle", "Regla", "Lineal", "Линейка", "자", "定規"),
    "aid_set_square_45": ("三角板45°", "45° set square", "Équerre 45°", "Escuadra 45°", "45°-Dreieck", "Угольник 45°", "45° 삼각자", "45°三角定規"),
    "aid_set_square_30": ("三角板30°", "30° set square", "Équerre 30°", "Escuadra 30°", "30°-Dreieck", "Угольник 30°", "30° 삼각자", "30°三角定規"),
    "aid_protractor": ("量角器", "Protractor", "Rapporteur", "Transportador", "Winkelmesser", "Транспортир", "각도기", "分度器"),
    "aid_clear_all": ("清除全部教具", "Remove all aids", "Retirer tous les outils", "Quitar todas las reglas", "Alle Hilfen entfernen", "Убрать все инструменты", "모든 도구 제거", "すべての作図ツールを削除"),
    "aid_hint": (
        "直尺悬停读 mm/cm，滚轮改变量程，Ctrl+滚轮改宽度\n量角器悬停读角，Shift 吸附整度\n青绿点旋转，橙色点缩放/量程，紫色方块调宽\n红色 ✕ 移除（触屏用它；鼠标右键同样可移除）",
        "Hover the ruler for mm/cm; wheel changes length, Ctrl+wheel changes width\nHover the protractor for the angle; hold Shift to snap to whole degrees\nTeal dot rotates, orange dot scales, purple square sets width\nRed ✕ removes it (use this on touch; right-click also works)",
        "Survolez la règle pour mm/cm ; molette = longueur, Ctrl+molette = largeur\nSurvolez le rapporteur pour l'angle ; Maj = degrés entiers\nPoint turquoise : rotation, orange : échelle, carré violet : largeur\n✕ rouge pour retirer (tactile ; clic droit aussi)",
        "Pase sobre la regla para mm/cm; rueda = longitud, Ctrl+rueda = ancho\nPase sobre el transportador para el ángulo; Mayús = grados enteros\nPunto turquesa: girar, naranja: escalar, cuadrado morado: ancho\n✕ rojo para quitar (táctil; clic derecho también)",
        "Lineal überfahren für mm/cm; Rad = Länge, Strg+Rad = Breite\nWinkelmesser überfahren für den Winkel; Umschalt = ganze Grad\nTürkiser Punkt dreht, oranger skaliert, violettes Quadrat = Breite\nRotes ✕ entfernt (für Touch; Rechtsklick geht auch)",
        "Наведите на линейку для мм/см; колесо — длина, Ctrl+колесо — ширина\nНаведите на транспортир для угла; Shift — целые градусы\nБирюзовая точка вращает, оранжевая масштабирует, фиолетовый квадрат — ширина\nКрасный ✕ убирает (для сенсора; ПКМ тоже)",
        "자에 올리면 mm/cm 표시, 휠로 길이, Ctrl+휠로 폭 조절\n각도기에 올리면 각도 표시, Shift로 정수 각도 스냅\n청록 점 회전, 주황 점 크기, 보라 사각형 폭\n빨간 ✕ 제거 (터치용, 우클릭도 가능)",
        "定規にホバーで mm/cm、ホイールで長さ、Ctrl+ホイールで幅\n分度器にホバーで角度、Shift で整数度スナップ\n青緑の点は回転、橙は拡大縮小、紫の四角は幅\n赤い ✕ で削除（タッチ用・右クリックも可）",
    ),
    "ruler_scale_dpi": ("直尺比例：DPI 估算", "Ruler scale: estimated from DPI", "Échelle : estimée via DPI", "Escala: estimada por DPI", "Maßstab: aus DPI geschätzt", "Масштаб: оценка по DPI", "자 배율: DPI 추정", "定規倍率: DPI 推定"),
    "calibrated_source": ("已校准", "calibrated", "calibré", "calibrado", "kalibriert", "откалибровано", "보정됨", "校正済み"),
    "dpi_source": ("DPI 估算", "DPI estimate", "estimation DPI", "estimación DPI", "DPI-Schätzung", "оценка по DPI", "DPI 추정", "DPI 推定"),
    "ruler_scale_value": ("直尺比例：{source} · {ratio} px/mm", "Ruler scale: {source} · {ratio} px/mm", "Échelle : {source} · {ratio} px/mm", "Escala: {source} · {ratio} px/mm", "Maßstab: {source} · {ratio} px/mm", "Масштаб: {source} · {ratio} px/mm", "자 배율: {source} · {ratio} px/mm", "定規倍率: {source} · {ratio} px/mm"),
    "calibrate_screen": ("校准当前屏幕", "Calibrate this screen", "Calibrer cet écran", "Calibrar esta pantalla", "Diesen Bildschirm kalibrieren", "Калибровать этот экран", "이 화면 보정", "この画面を校正"),
    "reset_to_dpi": ("恢复 DPI 估算", "Reset to DPI estimate", "Revenir à l'estimation DPI", "Volver a estimación DPI", "Auf DPI-Schätzung zurücksetzen", "Вернуть оценку по DPI", "DPI 추정으로 복원", "DPI 推定に戻す"),
    "calibration_title": ("校准当前屏幕直尺", "Calibrate the on-screen ruler", "Calibrer la règle à l'écran", "Calibrar la regla en pantalla", "Bildschirmlineal kalibrieren", "Калибровка экранной линейки", "화면 자 보정", "画面定規の校正"),
    "calibration_reference": ("实体参考长度：", "Physical reference length:", "Longueur de référence :", "Longitud de referencia:", "Referenzlänge:", "Эталонная длина:", "실제 기준 길이:", "実物の基準長:"),
    "calibration_hint": ("将实体直尺的 0 和参考长度分别对准上方两个圆点，拖动圆点后点击应用。", "Line a real ruler's 0 mark and the reference length up with the two dots above, then apply.", "Alignez le 0 d'une règle réelle et la longueur de référence sur les deux points, puis appliquez.", "Alinee el 0 de una regla real y la longitud de referencia con los dos puntos y aplique.", "Richten Sie die 0 eines echten Lineals und die Referenzlänge an den beiden Punkten aus und übernehmen Sie.", "Совместите 0 настоящей линейки и эталонную длину с двумя точками, затем примените.", "실제 자의 0과 기준 길이를 위 두 점에 맞춘 뒤 적용하세요.", "実物の定規の 0 と基準長を上の 2 点に合わせて適用してください。"),
    "calibration_apply": ("应用校准", "Apply calibration", "Appliquer", "Aplicar", "Übernehmen", "Применить", "보정 적용", "校正を適用"),
    "calibration_guide": ("屏幕校准参考线", "Screen calibration guide", "Repère de calibration", "Guía de calibración", "Kalibrierungslinie", "Линия калибровки", "화면 보정 기준선", "画面校正の基準線"),
    "calibration_length": ("当前线长：{value} Qt 像素", "Current length: {value} Qt pixels", "Longueur : {value} pixels Qt", "Longitud: {value} píxeles Qt", "Länge: {value} Qt-Pixel", "Длина: {value} пикс. Qt", "현재 길이: {value} Qt 픽셀", "現在の長さ: {value} Qt ピクセル"),
    "ruler_length_mm": ("直尺 {value} mm", "Ruler {value} mm", "Règle {value} mm", "Regla {value} mm", "Lineal {value} mm", "Линейка {value} мм", "자 {value} mm", "定規 {value} mm"),
    "timer_preset_min": ("{value}分", "{value} min", "{value} min", "{value} min", "{value} Min", "{value} мин", "{value}분", "{value}分"),
    "calc_state_error": ("错误", "Error", "Erreur", "Error", "Fehler", "Ошибка", "오류", "エラー"),
    "calc_state_overflow": ("溢出", "Overflow", "Dépassement", "Desbordamiento", "Überlauf", "Переполнение", "오버플로", "オーバーフロー"),
    "roster_import_title": ("导入人员名单", "Import a name list", "Importer une liste", "Importar lista", "Namensliste importieren", "Импорт списка имён", "명단 가져오기", "名簿を読み込む"),
    "calibration_invalid": ("校准无效", "Invalid calibration", "Calibration invalide", "Calibración inválida", "Ungültige Kalibrierung", "Неверная калибровка", "잘못된 보정", "キャリブレーション無効"),
    "calibration_invalid_msg": ("参考线长度与实体长度计算出的比例无效，请重新校准。", "The measured ratio is invalid. Please recalibrate.", "Le rapport mesuré est invalide. Veuillez recalibrer.", "La proporción medida no es válida. Vuelva a calibrar.", "Das gemessene Verhältnis ist ungültig. Bitte neu kalibrieren.", "Измеренное соотношение недействительно. Повторите калибровку.", "측정된 비율이 유효하지 않습니다. 다시 보정하세요.", "測定比率が無効です。再キャリブレーションしてください。"),

    # ---------- 计时器 ----------
    "timer": ("计时器", "Timer", "Minuteur", "Temporizador", "Timer", "Таймер", "타이머", "タイマー"),
    "timer_up": ("正计时", "Count up", "Chronomètre", "Cronómetro", "Aufwärts", "Секундомер", "스톱워치", "カウントアップ"),
    "timer_down": ("倒计时", "Count down", "Compte à rebours", "Cuenta atrás", "Abwärts", "Обратный отсчёт", "카운트다운", "カウントダウン"),
    "timer_start": ("开始", "Start", "Démarrer", "Iniciar", "Start", "Старт", "시작", "開始"),
    "timer_pause": ("暂停", "Pause", "Pause", "Pausa", "Pause", "Пауза", "일시정지", "一時停止"),
    "timer_reset": ("重置", "Reset", "Réinitialiser", "Reiniciar", "Zurücksetzen", "Сброс", "초기화", "リセット"),

    # ---------- 点名 ----------
    "roster": ("随机点名", "Random Name", "Nom aléatoire", "Nombre aleatorio", "Zufallsname", "Случайное имя", "무작위 이름", "ランダム名簿"),
    "roster_draw": ("点名", "Draw", "Tirer", "Sortear", "Ziehen", "Выбрать", "뽑기", "抽選"),
    "roster_reset": ("重置已点", "Reset drawn", "Réinitialiser", "Reiniciar sorteados", "Gezogene zurücksetzen", "Сбросить выбранных", "뽑은 기록 초기화", "抽選済みをリセット"),
    "roster_import": ("导入名单", "Import list", "Importer", "Importar lista", "Liste importieren", "Импорт списка", "명단 가져오기", "名簿を読み込む"),
    "roster_add": ("添加", "Add", "Ajouter", "Añadir", "Hinzufügen", "Добавить", "추가", "追加"),
    "roster_delete": ("删除", "Delete", "Supprimer", "Eliminar", "Löschen", "Удалить", "삭제", "削除"),
    "roster_start_hint": ("点击「点名」开始", "Tap “Draw” to start", "Touchez « Tirer »", "Toque «Sortear»", "„Ziehen“ antippen", "Нажмите «Выбрать»", "「뽑기」를 누르세요", "「抽選」を押してください"),
    "roster_stats": ("名单 {total} 人 · 已点 {drawn}", "{total} names · {drawn} drawn", "{total} noms · {drawn} tirés", "{total} nombres · {drawn} sorteados", "{total} Namen · {drawn} gezogen", "Имён: {total} · выбрано: {drawn}", "{total}명 · {drawn}명 뽑음", "{total} 名 · 抽選済み {drawn}"),
    "roster_empty": ("请先导入名单", "Import a list first", "Importez d'abord une liste", "Importe una lista primero", "Zuerst eine Liste importieren", "Сначала импортируйте список", "먼저 명단을 가져오세요", "先に名簿を読み込んでください"),
    "roster_reset_done": ("已重置", "Reset", "Réinitialisé", "Reiniciado", "Zurückgesetzt", "Сброшено", "초기화됨", "リセットしました"),
    "roster_file_hint": ("支持 txt/csv\n一行一个姓名", "txt / csv supported\none name per line", "txt / csv acceptés\nun nom par ligne", "txt / csv admitidos\nun nombre por línea", "txt / csv möglich\nein Name pro Zeile", "txt / csv\nпо одному имени в строке", "txt / csv 지원\n한 줄에 한 명", "txt / csv 対応\n1 行に 1 名"),
    "roster_add_title": ("添加姓名", "Add a name", "Ajouter un nom", "Añadir nombre", "Name hinzufügen", "Добавить имя", "이름 추가", "名前を追加"),
    "roster_add_label": ("姓名：", "Name:", "Nom :", "Nombre:", "Name:", "Имя:", "이름:", "名前:"),
    "roster_imported": ("已导入 {count} 人", "Imported {count} names", "{count} noms importés", "Se importaron {count}", "{count} Namen importiert", "Импортировано: {count}", "{count}명 가져옴", "{count} 名を読み込みました"),

    # ---------- 计算器 ----------
    "calculator": ("计算器", "Calculator", "Calculatrice", "Calculadora", "Rechner", "Калькулятор", "계산기", "電卓"),
    "copy_result": ("复制结果", "Copy result", "Copier", "Copiar resultado", "Ergebnis kopieren", "Копировать результат", "결과 복사", "結果をコピー"),
    "calc_invalid": ("表达式无效", "Invalid expression", "Expression invalide", "Expresión no válida", "Ungültiger Ausdruck", "Неверное выражение", "잘못된 수식", "無効な式"),
    "calc_too_long": ("表达式过长", "Expression too long", "Expression trop longue", "Expresión demasiado larga", "Ausdruck zu lang", "Выражение слишком длинное", "수식이 너무 깁니다", "式が長すぎます"),
    "calc_overflow": ("结果溢出", "Result out of range", "Résultat hors limites", "Resultado fuera de rango", "Ergebnis außerhalb des Bereichs", "Результат вне диапазона", "결과 범위 초과", "結果が範囲外です"),
    "calc_error": ("计算错误", "Calculation error", "Erreur de calcul", "Error de cálculo", "Rechenfehler", "Ошибка вычисления", "계산 오류", "計算エラー"),
    "calc_unsupported": ("不支持的表达式", "Unsupported expression", "Expression non prise en charge", "Expresión no admitida", "Nicht unterstützter Ausdruck", "Неподдерживаемое выражение", "지원하지 않는 수식", "サポートされない式"),
    "calc_too_large": ("数值过大", "Number too large", "Nombre trop grand", "Número demasiado grande", "Zahl zu groß", "Слишком большое число", "숫자가 너무 큽니다", "数値が大きすぎます"),

    # ---------- 文本 ----------
    "text_input_title": ("输入文字", "Enter text", "Saisir le texte", "Escribir texto", "Text eingeben", "Введите текст", "텍스트 입력", "テキストを入力"),
    "text_input_label": ("文字内容：", "Text:", "Texte :", "Texto:", "Text:", "Текст:", "내용:", "内容:"),

    # ---------- 文件 ----------
    "file": ("文件", "File", "Fichier", "Archivo", "Datei", "Файл", "파일", "ファイル"),
    "project_group": ("项目", "Project", "Projet", "Proyecto", "Projekt", "Проект", "프로젝트", "プロジェクト"),
    "import_group": ("导入", "Import", "Importer", "Importar", "Import", "Импорт", "가져오기", "読み込み"),
    "export_group": ("导出", "Export", "Exporter", "Exportar", "Export", "Экспорт", "내보내기", "書き出し"),
    "save_project_as": ("另存为", "Save As", "Enregistrer sous", "Guardar como", "Speichern unter", "Сохранить как", "다른 이름으로 저장", "名前を付けて保存"),

    # ---------- 导入 / 导出 ----------
    "export": ("导出", "Export", "Exporter", "Exportar", "Exportieren", "Экспорт", "내보내기", "エクスポート"),
    "export_format": ("选择导出格式", "Choose export format", "Choisir le format", "Elegir formato", "Exportformat wählen", "Формат экспорта", "내보내기 형식", "形式を選択"),
    "export_png": ("PNG 图片", "PNG Image", "Image PNG", "Imagen PNG", "PNG-Bild", "PNG-изображение", "PNG 이미지", "PNG 画像"),
    "export_pdf": ("PDF 文档", "PDF Document", "Document PDF", "Documento PDF", "PDF-Dokument", "PDF-документ", "PDF 문서", "PDF 文書"),
    "export_svg": ("SVG 矢量图", "SVG Vector", "Vectoriel SVG", "Vector SVG", "SVG-Vektor", "SVG-вектор", "SVG 벡터", "SVG ベクター"),
    "export_eps": ("EPS 矢量图", "EPS Vector", "Vectoriel EPS", "Vector EPS", "EPS-Vektor", "EPS-вектор", "EPS 벡터", "EPS ベクター"),
    "export_done": ("导出完成", "Export complete", "Export terminé", "Exportación completa", "Export abgeschlossen", "Экспорт завершён", "내보내기 완료", "エクスポート完了"),
    "export_failed": ("导出失败", "Export failed", "Échec de l'export", "Error al exportar", "Export fehlgeschlagen", "Ошибка экспорта", "내보내기 실패", "エクスポート失敗"),
    "export_png_summary": ("已导出 {count} 张 PNG\n{path}", "Exported {count} PNG file(s)\n{path}", "{count} PNG exporté(s)\n{path}", "Se exportaron {count} PNG\n{path}", "{count} PNG exportiert\n{path}", "Экспортировано PNG: {count}\n{path}", "PNG {count}개 내보냄\n{path}", "PNG {count} 件を出力\n{path}"),
    "export_pdf_summary": ("已导出 {count} 页 PDF\n{path}", "Exported {count}-page PDF\n{path}", "PDF de {count} page(s) exporté\n{path}", "PDF de {count} página(s)\n{path}", "{count}-seitiges PDF exportiert\n{path}", "PDF на {count} стр.\n{path}", "{count}페이지 PDF 내보냄\n{path}", "{count} ページの PDF を出力\n{path}"),
    "export_svg_summary": ("已导出 {count} 个 SVG\n{path}", "Exported {count} SVG file(s)\n{path}", "{count} SVG exporté(s)\n{path}", "Se exportaron {count} SVG\n{path}", "{count} SVG exportiert\n{path}", "Экспортировано SVG: {count}\n{path}", "SVG {count}개 내보냄\n{path}", "SVG {count} 件を出力\n{path}"),
    "export_eps_summary": ("已导出 {count} 个 EPS\n{path}", "Exported {count} EPS file(s)\n{path}", "{count} EPS exporté(s)\n{path}", "Se exportaron {count} EPS\n{path}", "{count} EPS exportiert\n{path}", "Экспортировано EPS: {count}\n{path}", "EPS {count}개 내보냄\n{path}", "EPS {count} 件を出力\n{path}"),
    "export_hint": ("白板：逐页导出（含页码）\n批注：截取屏幕\nSVG/EPS 为矢量，可再编辑", "Whiteboard: page by page (with numbers)\nAnnotate: screen capture\nSVG/EPS are vector and stay editable", "Tableau : page par page (numérotées)\nAnnotation : capture\nSVG/EPS restent vectoriels", "Pizarra: página a página (numeradas)\nAnotar: captura\nSVG/EPS son vectoriales", "Whiteboard: seitenweise (nummeriert)\nAnnotieren: Screenshot\nSVG/EPS bleiben vektoriell", "Доска: постранично (с номерами)\nАннотация: снимок\nSVG/EPS — вектор", "화이트보드: 페이지별 (번호 포함)\n주석: 화면 캡처\nSVG/EPS는 벡터", "ホワイトボード: ページごと (番号付き)\n注釈: 画面キャプチャ\nSVG/EPS はベクター"),
    "export_whiteboard_only": (
        "SVG/EPS 矢量导出仅支持白板模式（逐页）。\n批注模式请使用 PNG / PDF（屏幕截屏导出）。",
        "SVG/EPS vector export is only available in whiteboard mode (page by page).\nFor annotation mode use PNG / PDF (screen capture).",
        "L'export vectoriel SVG/EPS n'est disponible qu'en mode tableau (page par page).\nEn mode annotation, utilisez PNG / PDF (capture d'écran).",
        "La exportación vectorial SVG/EPS solo está disponible en modo pizarra (página a página).\nEn modo anotación use PNG / PDF (captura de pantalla).",
        "SVG/EPS-Vektor-Export nur im Whiteboard-Modus (seitenweise) verfügbar.\nIm Annotationsmodus PNG / PDF verwenden (Bildschirmaufnahme).",
        "Векторный экспорт SVG/EPS доступен только в режиме доски (постранично).\nВ режиме аннотаций используйте PNG / PDF (снимок экрана).",
        "SVG/EPS 벡터 내보내기는 화이트보드 모드(페이지별)에서만 가능합니다.\n주석 모드에서는 PNG / PDF(화면 캡처)를 사용하세요.",
        "SVG/EPS ベクター書き出しはホワイトボードモード（ページごと）のみ可能です。\n注釈モードでは PNG / PDF（画面キャプチャ）をご利用ください。",
    ),
    "import_media": ("导入图片/PDF", "Import image / PDF", "Importer image / PDF", "Importar imagen / PDF", "Bild / PDF importieren", "Импорт изображения / PDF", "이미지/PDF 가져오기", "画像/PDF を読み込む"),
    "import_media_filter": ("图片与 PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;图片 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF 文档 (*.pdf);;所有文件 (*.*)", "Images and PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;All files (*.*)", "Images et PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;Tous (*.*)", "Imágenes y PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;Imágenes (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;Todos (*.*)", "Bilder und PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;Bilder (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;Alle (*.*)", "Изображения и PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;Изображения (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;Все файлы (*.*)", "이미지 및 PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;이미지 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;모든 파일 (*.*)", "画像と PDF (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.pdf);;画像 (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;PDF (*.pdf);;すべて (*.*)"),
    "import_done": ("导入完成", "Import complete", "Import terminé", "Importación completa", "Import abgeschlossen", "Импорт завершён", "가져오기 완료", "読み込み完了"),
    "import_failed": ("导入失败", "Import failed", "Échec de l'import", "Error al importar", "Import fehlgeschlagen", "Ошибка импорта", "가져오기 실패", "インポート失敗"),
    "import_image_summary": ("已插入图片：{name}", "Inserted image: {name}", "Image insérée : {name}", "Imagen insertada: {name}", "Bild eingefügt: {name}", "Вставлено изображение: {name}", "이미지 삽입됨: {name}", "画像を挿入: {name}"),
    "import_pdf_summary": ("已导入 PDF {count} 页：{name}", "Imported {count} PDF page(s): {name}", "{count} page(s) PDF importée(s) : {name}", "Se importaron {count} páginas PDF: {name}", "{count} PDF-Seite(n) importiert: {name}", "Импортировано страниц PDF: {count} — {name}", "PDF {count}페이지 가져옴: {name}", "PDF {count} ページを読み込み: {name}"),
    "import_pdf_unsupported": ("当前环境缺少 PyQt6 的 QtPdf 模块，无法导入 PDF。可改为先把 PDF 导出成图片再导入。", "This build has no QtPdf module, so PDF import is unavailable. Export the PDF to images first.", "Ce build n'a pas QtPdf : import PDF indisponible. Convertissez d'abord le PDF en images.", "Esta compilación no incluye QtPdf: no se puede importar PDF. Conviértalo a imágenes primero.", "Dieser Build hat kein QtPdf-Modul, daher kein PDF-Import. Wandeln Sie das PDF zuerst in Bilder um.", "В этой сборке нет модуля QtPdf, импорт PDF недоступен. Сначала преобразуйте PDF в изображения.", "이 빌드에는 QtPdf 모듈이 없어 PDF를 가져올 수 없습니다. 먼저 이미지로 변환하세요.", "このビルドには QtPdf がないため PDF を読み込めません。先に画像へ変換してください。"),
    "import_pdf_pages_limited": ("PDF 页数较多，仅导入前 {count} 页。", "The PDF is long; only the first {count} pages were imported.", "PDF long : seules les {count} premières pages ont été importées.", "El PDF es largo; solo se importaron las primeras {count} páginas.", "Das PDF ist lang; nur die ersten {count} Seiten wurden importiert.", "PDF большой: импортированы первые {count} страниц.", "PDF가 길어 처음 {count}페이지만 가져왔습니다.", "PDF が長いため最初の {count} ページのみ読み込みました。"),

    # ---------- 项目文件 ----------
    "save_project": ("保存项目", "Save project", "Enregistrer le projet", "Guardar proyecto", "Projekt speichern", "Сохранить проект", "프로젝트 저장", "プロジェクトを保存"),
    "open_project": ("打开项目", "Open project", "Ouvrir un projet", "Abrir proyecto", "Projekt öffnen", "Открыть проект", "프로젝트 열기", "プロジェクトを開く"),
    "project_filter_save": ("MyScreenDraw 项目 (*.msd);;JSON 文件 (*.json)", "MyScreenDraw project (*.msd);;JSON file (*.json)", "Projet MyScreenDraw (*.msd);;Fichier JSON (*.json)", "Proyecto MyScreenDraw (*.msd);;Archivo JSON (*.json)", "MyScreenDraw-Projekt (*.msd);;JSON-Datei (*.json)", "Проект MyScreenDraw (*.msd);;Файл JSON (*.json)", "MyScreenDraw 프로젝트 (*.msd);;JSON 파일 (*.json)", "MyScreenDraw プロジェクト (*.msd);;JSON ファイル (*.json)"),
    "project_filter_open": ("MyScreenDraw 项目 (*.msd *.json)", "MyScreenDraw project (*.msd *.json)", "Projet MyScreenDraw (*.msd *.json)", "Proyecto MyScreenDraw (*.msd *.json)", "MyScreenDraw-Projekt (*.msd *.json)", "Проект MyScreenDraw (*.msd *.json)", "MyScreenDraw 프로젝트 (*.msd *.json)", "MyScreenDraw プロジェクト (*.msd *.json)"),
    "roster_filter": ("文本/CSV (*.txt *.csv);;所有文件 (*.*)", "Text / CSV (*.txt *.csv);;All files (*.*)", "Texte / CSV (*.txt *.csv);;Tous (*.*)", "Texto / CSV (*.txt *.csv);;Todos (*.*)", "Text / CSV (*.txt *.csv);;Alle (*.*)", "Текст / CSV (*.txt *.csv);;Все файлы (*.*)", "텍스트/CSV (*.txt *.csv);;모든 파일 (*.*)", "テキスト/CSV (*.txt *.csv);;すべて (*.*)"),

    # ---------- 错误与提示 ----------
    "save_failed": ("保存失败", "Save failed", "Échec de l'enregistrement", "Error al guardar", "Speichern fehlgeschlagen", "Ошибка сохранения", "저장 실패", "保存に失敗"),
    "open_failed": ("打开失败", "Open failed", "Échec de l'ouverture", "Error al abrir", "Öffnen fehlgeschlagen", "Ошибка открытия", "열기 실패", "開くに失敗"),
    "restore_failed": ("恢复失败", "Restore failed", "Échec de la restauration", "Error al restaurar", "Wiederherstellen fehlgeschlagen", "Ошибка восстановления", "복원 실패", "復元失敗"),
    "restore_autosave": ("恢复自动保存", "Restore autosave", "Restaurer la sauvegarde auto", "Restaurar autoguardado", "Autosave wiederherstellen", "Восстановить автосохранение", "자동 저장 복원", "自動保存を復元"),
    "no_screen": ("没有可用的屏幕用于截图", "No screen available for capture", "Aucun écran disponible", "No hay pantalla disponible", "Kein Bildschirm verfügbar", "Нет экрана для захвата", "캡처할 화면이 없습니다", "キャプチャできる画面がありません"),

    # 具体错误原因：给用户可执行的下一步，而不是抛 Python 异常文本
    "err_file_missing": ("找不到文件：\n{path}\n\n它可能已被移动、重命名或删除。", "File not found:\n{path}\n\nIt may have been moved, renamed or deleted.", "Fichier introuvable :\n{path}\n\nIl a pu être déplacé, renommé ou supprimé.", "Archivo no encontrado:\n{path}\n\nPuede haberse movido, renombrado o eliminado.", "Datei nicht gefunden:\n{path}\n\nSie wurde evtl. verschoben, umbenannt oder gelöscht.", "Файл не найден:\n{path}\n\nВозможно, он перемещён, переименован или удалён.", "파일을 찾을 수 없습니다:\n{path}\n\n이동, 이름 변경 또는 삭제되었을 수 있습니다.", "ファイルが見つかりません:\n{path}\n\n移動・改名・削除された可能性があります。"),
    "err_permission": ("没有权限访问：\n{path}\n\n请把程序或文件放到有写入权限的位置（例如桌面或 D 盘），\n避免使用 C:\\Program Files。", "Permission denied:\n{path}\n\nPut the program or file somewhere writable (Desktop or another drive)\nrather than C:\\Program Files.", "Accès refusé :\n{path}\n\nPlacez le programme ou le fichier dans un dossier accessible en écriture,\npas dans C:\\Program Files.", "Permiso denegado:\n{path}\n\nColoque el programa o archivo en una ubicación con permiso de escritura,\nno en C:\\Program Files.", "Zugriff verweigert:\n{path}\n\nLegen Sie Programm oder Datei an einen beschreibbaren Ort,\nnicht nach C:\\Program Files.", "Отказано в доступе:\n{path}\n\nПоместите программу или файл в доступную для записи папку,\nа не в C:\\Program Files.", "권한이 없습니다:\n{path}\n\n쓰기 가능한 위치(바탕화면 등)에 두세요.\nC:\\Program Files는 피하세요.", "アクセスできません:\n{path}\n\n書き込み可能な場所に置いてください。\nC:\\Program Files は避けてください。"),
    "err_disk_full": ("磁盘空间不足，无法写入：\n{path}", "Not enough disk space to write:\n{path}", "Espace disque insuffisant :\n{path}", "Espacio en disco insuficiente:\n{path}", "Nicht genug Speicherplatz:\n{path}", "Недостаточно места на диске:\n{path}", "디스크 공간이 부족합니다:\n{path}", "ディスク容量が不足しています:\n{path}"),
    "err_io": ("读写文件时出错：\n{path}\n\n{detail}", "Error while reading or writing:\n{path}\n\n{detail}", "Erreur de lecture/écriture :\n{path}\n\n{detail}", "Error de lectura/escritura:\n{path}\n\n{detail}", "Fehler beim Lesen/Schreiben:\n{path}\n\n{detail}", "Ошибка чтения/записи:\n{path}\n\n{detail}", "읽기/쓰기 오류:\n{path}\n\n{detail}", "読み書きエラー:\n{path}\n\n{detail}"),
    "err_bad_json": ("文件格式不正确，无法解析：\n{path}\n\n它可能不是 MyScreenDraw 项目文件，或已损坏。", "This file is not valid and cannot be parsed:\n{path}\n\nIt may not be a MyScreenDraw project, or it is damaged.", "Fichier illisible :\n{path}\n\nCe n'est peut-être pas un projet MyScreenDraw, ou il est endommagé.", "Archivo no válido:\n{path}\n\nPuede no ser un proyecto MyScreenDraw o estar dañado.", "Datei ungültig:\n{path}\n\nEvtl. kein MyScreenDraw-Projekt oder beschädigt.", "Файл повреждён или не читается:\n{path}\n\nВозможно, это не проект MyScreenDraw.", "파일을 해석할 수 없습니다:\n{path}\n\nMyScreenDraw 프로젝트가 아니거나 손상되었습니다.", "ファイルを解析できません:\n{path}\n\nMyScreenDraw のプロジェクトでないか破損しています。"),
    "err_invalid_project": ("项目内容不合法：\n{detail}\n\n为避免载入损坏的数据，本次打开已取消。", "The project contents are invalid:\n{detail}\n\nOpening was cancelled so no damaged data is loaded.", "Contenu de projet invalide :\n{detail}\n\nOuverture annulée.", "Contenido de proyecto no válido:\n{detail}\n\nSe canceló la apertura.", "Projektinhalt ungültig:\n{detail}\n\nÖffnen abgebrochen.", "Недопустимое содержимое проекта:\n{detail}\n\nОткрытие отменено.", "프로젝트 내용이 올바르지 않습니다:\n{detail}\n\n열기를 취소했습니다.", "プロジェクトの内容が不正です:\n{detail}\n\n読み込みを中止しました。"),
    "err_file_too_large": ("文件过大，已拒绝打开：\n{path}\n\n上限为 {limit}。", "File too large, refused:\n{path}\n\nThe limit is {limit}.", "Fichier trop volumineux :\n{path}\n\nLimite : {limit}.", "Archivo demasiado grande:\n{path}\n\nLímite: {limit}.", "Datei zu groß:\n{path}\n\nGrenze: {limit}.", "Файл слишком большой:\n{path}\n\nПредел: {limit}.", "파일이 너무 큽니다:\n{path}\n\n한도: {limit}.", "ファイルが大きすぎます:\n{path}\n\n上限: {limit}。"),
    "err_unsupported_image": ("无法识别这张图片：\n{path}\n\n请改用 PNG、JPG、BMP、GIF 或 WEBP。", "This image could not be read:\n{path}\n\nTry PNG, JPG, BMP, GIF or WEBP.", "Image illisible :\n{path}\n\nEssayez PNG, JPG, BMP, GIF ou WEBP.", "No se pudo leer la imagen:\n{path}\n\nUse PNG, JPG, BMP, GIF o WEBP.", "Bild nicht lesbar:\n{path}\n\nVersuchen Sie PNG, JPG, BMP, GIF oder WEBP.", "Не удалось прочитать изображение:\n{path}\n\nИспользуйте PNG, JPG, BMP, GIF или WEBP.", "이미지를 읽을 수 없습니다:\n{path}\n\nPNG, JPG, BMP, GIF, WEBP를 사용하세요.", "画像を読み込めません:\n{path}\n\nPNG・JPG・BMP・GIF・WEBP をお試しください。"),
    "err_window_create": ("窗口创建失败：{detail}\n\n请尝试重启程序；若反复出现，请附上 data/app.log 反馈。", "Could not create the window: {detail}\n\nRestart the program; if it keeps happening, report it with data/app.log.", "Échec de création de fenêtre : {detail}\n\nRedémarrez ; si cela persiste, joignez data/app.log.", "No se pudo crear la ventana: {detail}\n\nReinicie; si persiste, adjunte data/app.log.", "Fenster konnte nicht erstellt werden: {detail}\n\nNeu starten; bei Wiederholung data/app.log melden.", "Не удалось создать окно: {detail}\n\nПерезапустите; если повторяется, приложите data/app.log.", "창을 만들 수 없습니다: {detail}\n\n재시작하세요. 반복되면 data/app.log와 함께 알려주세요.", "ウィンドウを作成できません: {detail}\n\n再起動してください。繰り返す場合は data/app.log を添えてご報告ください。"),
}

# 每个条目都必须给全 8 种语言：漏一个就在导入时炸掉，而不是在课堂上显示成英文 key。
for _key, _values in _BASE.items():
    if len(_values) != len(_LANGS):
        raise ValueError(f"i18n key {_key!r} has {len(_values)} translations, expected {len(_LANGS)}")

TEXT = {lang: {key: values[idx] for key, values in _BASE.items()} for idx, lang in enumerate(_LANGS)}


def system_language() -> str:
    return SUPPORTED.get(QLocale.system().language(), "en")


CURRENT = system_language()


def set_language(lang: str) -> str:
    """切换界面语言（需重建界面文案才会全部生效）。返回实际生效的语言码。"""
    global CURRENT
    if lang in TEXT:
        CURRENT = lang
    return CURRENT


def tr(key: str) -> str:
    return TEXT.get(CURRENT, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def trf(key: str, **kwargs) -> str:
    """带占位符的文案。缺参数时回退到模板本身，绝不因为翻译写错而抛异常。"""
    template = tr(key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template
