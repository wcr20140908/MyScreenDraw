# SPDX-License-Identifier: GPL-3.0-or-later
"""C04 text only, tuple order: zh, en, fr, es, de, ru, ko, ja."""

SELECTION_COPY = {
    'teaching_group_editing': ('编辑与页面', 'Editing and pages', 'Édition et pages', 'Edición y páginas', 'Bearbeiten und Seiten', 'Редактирование и страницы', '편집과 페이지', '編集とページ'),
    'teaching_c04_title': ('选择与编辑', 'Selection and editing', 'Sélection et édition', 'Selección y edición', 'Auswählen und Bearbeiten', 'Выбор и редактирование', '선택과 편집', '選択と編集'),
    'teaching_c04_select_move_title': ('选取并移动对象', 'Select and move objects', 'Sélectionner et déplacer', 'Seleccionar y mover objetos', 'Objekte auswählen und bewegen', 'Выбор и перемещение объектов', '개체 선택 및 이동', 'オブジェクトの選択と移動'),
    'teaching_c04_transform_title': ('缩放与旋转控制柄', 'Scale and rotate handles', 'Poignées de taille et rotation', 'Controles de tamaño y giro', 'Griffe zum Skalieren und Drehen', 'Маркеры масштаба и поворота', '크기 조절 및 회전 핸들', '拡大縮小と回転のハンドル'),
    'teaching_c04_copy_delete_title': ('框选、复制与删除', 'Box select, copy and delete', 'Sélection par cadre, copie et suppression', 'Selección por marco, copia y borrado', 'Rahmenauswahl, Kopieren und Löschen', 'Выбор рамкой, копирование и удаление', '영역 선택, 복사 및 삭제', '範囲選択・複製・削除'),
}

_STEP_TEXT = {
    'intro': (
        ('开始独立编辑练习', 'Start independent editing practice', 'Commencer cet exercice indépendant', 'Iniciar la práctica de edición', 'Separate Bearbeitungsübung starten', 'Начните отдельное упражнение', '독립 편집 연습 시작', '独立した編集練習を開始'),
        ('本章使用独立样例练习选择与编辑，原工作不会改变。点击“下一步”开始；跳过不计完成，退出教学可回到原工作。',
         'Practice selection and editing with separate samples; your original work stays protected. Select “Next step” to begin; skipping is not completion, and “Exit tutorial” returns to your work.',
         'Exercez-vous à sélectionner et modifier des exemples séparés ; votre travail initial reste protégé. Cliquez sur « Étape suivante » ; passer le chapitre ne le termine pas et quitter le tutoriel vous rend votre travail.',
         'Practica la selección y edición con ejemplos independientes; tu trabajo original queda protegido. Pulsa «Paso siguiente»; omitir no cuenta como completar y salir del tutorial te devuelve a tu trabajo.',
         'Üben Sie Auswahl und Bearbeitung an separaten Beispielen; Ihre ursprüngliche Arbeit bleibt geschützt. Wählen Sie „Nächster Schritt“; Überspringen zählt nicht als Abschluss, und das Beenden führt zur ursprünglichen Arbeit zurück.',
         'Практикуйте выбор и редактирование на отдельных примерах; исходная работа защищена. Нажмите «Следующий шаг»; пропуск не считается завершением, а выход из обучения вернёт исходную работу.',
         '독립된 예제로 선택과 편집을 연습하며 원래 작업은 보호됩니다. “다음 단계”를 누르세요. 건너뛰기는 완료로 계산되지 않으며 교육을 종료하면 원래 작업으로 돌아갑니다.',
         '独立したサンプルで選択と編集を練習し、元の作業は保護されます。「次のステップ」で開始します。スキップは完了に数えず、チュートリアルを終了すると元の作業に戻ります。')),
    'tool': (
        ('切到框选工具', 'Switch to Select', 'Passer à Sélection', 'Cambiar a Seleccionar', 'Zu Auswählen wechseln', 'Переключитесь на Выбор', '선택 도구로 전환', '選択ツールへ切り替え'),
        ('点击工具栏“框选”，实际切换到选择工具。这里只选择工具，选中样例要在下一步单独操作。',
         'Select “Select” on the toolbar to change the active tool. This chooses the tool; selecting a sample is a separate next action.',
         'Cliquez sur « Sélection » dans la barre pour changer d’outil. Le choix d’un exemple se fait séparément à l’étape suivante.',
         'Pulsa «Seleccionar» en la barra para cambiar la herramienta activa. Elegir el ejemplo será una acción distinta en el paso siguiente.',
         'Wählen Sie „Auswählen“ in der Werkzeugleiste. Ein Beispiel wählen Sie erst in der nächsten, separaten Aktion aus.',
         'Нажмите «Выбор» на панели инструментов. Сам пример нужно выбрать отдельно на следующем шаге.',
         '도구 모음의 “선택”을 눌러 활성 도구를 바꾸세요. 예제 선택은 다음 단계에서 별도로 수행합니다.',
         'ツールバーの「選択」を押してツールを切り替えます。サンプルの選択は次のステップで別に行います。')),
    'select': (
        ('单击选中样例', 'Click to select the sample', 'Cliquer pour choisir l’exemple', 'Haz clic para seleccionar el ejemplo', 'Beispiel durch Klick auswählen', 'Выберите пример щелчком', '예제를 클릭하여 선택', 'サンプルをクリックして選択'),
        ('在样例笔迹上单击并抬起，出现选中框后才算完成。此步先不要拖动；点击空白或已选对象不会完成新的选择。',
         'Click the sample stroke and release to show its selection box. Do not drag yet; blank clicks or selecting the same object again do not complete a new selection.',
         'Cliquez sur le trait et relâchez pour afficher son cadre. Ne le déplacez pas encore ; un clic dans le vide ou sur le même objet déjà choisi ne crée pas une nouvelle sélection.',
         'Haz clic en el trazo y suelta para mostrar su marco. Aún no arrastres; hacer clic en blanco o repetir la selección no crea una selección nueva.',
         'Klicken Sie auf den Beispielstrich und lassen Sie los, damit der Auswahlrahmen erscheint. Noch nicht ziehen; ein Klick ins Leere oder auf dieselbe Auswahl zählt nicht als neue Auswahl.',
         'Щёлкните по штриху и отпустите кнопку, чтобы появилась рамка. Пока не тяните; пустое место или повторный выбор того же объекта не создают новый выбор.',
         '예제 선을 클릭하고 놓아 선택 테두리를 표시하세요. 아직 끌지 마세요. 빈 곳이나 이미 선택된 개체를 클릭하면 새 선택으로 인정되지 않습니다.',
         'サンプルの線をクリックして離し、選択枠を表示します。まだドラッグしません。空白や同じ選択済みオブジェクトのクリックは新たな選択になりません。')),
    'move': (
        ('拖动并提交移动', 'Drag and commit a move', 'Déplacer puis relâcher', 'Arrastra y confirma el movimiento', 'Ziehen und Bewegung abschließen', 'Перетащите и завершите перемещение', '끌어서 이동 확정', 'ドラッグして移動を確定'),
        ('按住选中框内部，把样例拖到新位置，再抬起。原地点击或拖回原位不会完成移动。',
         'Press inside the selection box, drag the sample to a new location and release. A click without movement or dragging back to the starting point does not complete the move.',
         'Appuyez dans le cadre, déplacez l’exemple puis relâchez. Un simple clic ou un retour au point de départ ne termine pas le déplacement.',
         'Presiona dentro del marco, arrastra el ejemplo a otro lugar y suelta. Un clic sin movimiento o volver al punto inicial no completa el movimiento.',
         'Drücken Sie im Auswahlrahmen, ziehen Sie das Beispiel an eine neue Stelle und lassen Sie los. Ein Klick ohne Bewegung oder die Rückkehr zum Ausgangspunkt zählt nicht.',
         'Нажмите внутри рамки, перенесите пример в новое место и отпустите кнопку. Щелчок без движения или возврат в исходную точку не завершает перемещение.',
         '선택 테두리 안을 누르고 새 위치로 끈 뒤 놓으세요. 제자리 클릭이나 원래 위치로 되돌리는 동작은 이동 완료로 인정되지 않습니다.',
         '選択枠の内側を押し、別の位置へドラッグして離します。動かさずにクリックしたり元の位置へ戻したりしても移動完了にはなりません。')),
    'handles': (
        ('认识两个控制柄', 'Find the two handles', 'Repérer les deux poignées', 'Identifica los dos controles', 'Die zwei Griffe finden', 'Найдите два маркера', '두 핸들 확인', '二つのハンドルを確認'),
        ('右下角控制柄用于缩放，选中框上方控制柄用于旋转。先观察位置，点击“下一步”后再分别拖动。',
         'The lower right handle scales; the handle above the box rotates. Find both, then select “Next step” before dragging each one.',
         'La poignée en bas à droite change la taille ; celle au-dessus du cadre fait tourner. Repérez-les, puis cliquez sur « Étape suivante » avant de les utiliser.',
         'El control inferior derecho cambia el tamaño; el situado sobre el marco gira. Localízalos y pulsa «Paso siguiente» antes de arrastrarlos.',
         'Der Griff unten rechts skaliert, der oberhalb des Rahmens dreht. Sehen Sie sich beide an und wählen Sie vor dem Ziehen „Nächster Schritt“.',
         'Маркер справа внизу меняет масштаб, а маркер над рамкой поворачивает. Найдите их и нажмите «Следующий шаг», затем используйте каждый отдельно.',
         '오른쪽 아래 핸들은 크기를 조절하고 테두리 위 핸들은 회전합니다. 위치를 확인한 뒤 “다음 단계”를 누르고 각각 끌어 보세요.',
         '右下のハンドルは拡大縮小、枠の上にあるハンドルは回転に使います。位置を確認し、「次のステップ」の後でそれぞれドラッグします。')),
    'scale': (
        ('拖动右下角缩放柄', 'Drag the lower right scale handle', 'Tirer la poignée de taille', 'Arrastra el control de tamaño', 'Den Skalierungsgriff ziehen', 'Потяните маркер масштаба', '오른쪽 아래 크기 핸들 끌기', '右下の拡大縮小ハンドルをドラッグ'),
        ('按住右下角控制柄，改变样例大小后抬起。需要实际大小变化；点击不动或拖回原大小不会完成。',
         'Press the lower right handle, change the sample size and release. The size must actually change; no movement or returning to the original size does not complete this step.',
         'Appuyez sur la poignée en bas à droite, changez la taille puis relâchez. Un clic immobile ou un retour à la taille initiale ne termine pas l’étape.',
         'Presiona el control inferior derecho, cambia el tamaño y suelta. Sin cambio real o al volver al tamaño inicial, el paso no se completa.',
         'Ziehen Sie den Griff unten rechts, ändern Sie die Größe und lassen Sie los. Ohne Änderung oder bei Rückkehr zur ursprünglichen Größe wird der Schritt nicht abgeschlossen.',
         'Нажмите маркер справа внизу, измените размер и отпустите кнопку. Без изменения или при возврате к исходному размеру шаг не завершится.',
         '오른쪽 아래 핸들을 눌러 크기를 바꾼 뒤 놓으세요. 움직이지 않거나 원래 크기로 되돌리면 완료되지 않습니다.',
         '右下のハンドルを押してサイズを変え、離します。動かさない場合や元のサイズに戻した場合は完了しません。')),
    'rotate': (
        ('拖动上方旋转柄', 'Drag the upper rotation handle', 'Tirer la poignée de rotation', 'Arrastra el control de giro', 'Den oberen Drehgriff ziehen', 'Потяните верхний маркер поворота', '위쪽 회전 핸들 끌기', '上の回転ハンドルをドラッグ'),
        ('按住选中框上方控制柄，绕对象中心转动，再抬起。最终方向需要改变；转回原方向不会完成。',
         'Press the handle above the selection box, turn around the object center and release. The final direction must change; returning to the original angle does not complete this step.',
         'Appuyez sur la poignée au-dessus du cadre, tournez autour du centre puis relâchez. L’orientation finale doit changer ; revenir à l’angle initial ne termine pas l’étape.',
         'Presiona el control sobre el marco, gira alrededor del centro y suelta. La dirección final debe cambiar; volver al ángulo inicial no completa el paso.',
         'Ziehen Sie den Griff oberhalb des Rahmens um die Objektmitte und lassen Sie los. Die endgültige Richtung muss sich ändern; eine Rückkehr zum alten Winkel zählt nicht.',
         'Нажмите маркер над рамкой, поверните вокруг центра объекта и отпустите кнопку. Итоговое направление должно измениться; возврат к исходному углу не завершает шаг.',
         '테두리 위 핸들을 누르고 개체 중심을 기준으로 돌린 뒤 놓으세요. 최종 방향이 바뀌어야 하며 원래 방향으로 되돌리면 완료되지 않습니다.',
         '枠の上のハンドルを押し、中心の周りに回して離します。最終的な向きを変える必要があり、元の角度へ戻すと完了しません。')),
    'box': (
        ('从空白框选两个样例', 'Box select both samples', 'Encadrer les deux exemples', 'Selecciona ambos con un marco', 'Beide Beispiele mit Rahmen auswählen', 'Выберите рамкой оба примера', '빈 곳에서 두 예제 영역 선택', '空白から二つのサンプルを範囲選択'),
        ('从样例左上方空白开始，拖出包含两个矩形的选框，再抬起。必须框选到两个样例；单击一个或空框不算完成。当前矩形框选用于图形和图片，笔迹与文字请单击选取。',
         'Start in blank space above and left, draw a selection box around both rectangles and release. Both must be box selected; one click or an empty box is not enough. Box selection currently selects shapes and images; select strokes and text with a click.',
         'Partez du vide en haut à gauche, encadrez les deux rectangles puis relâchez. Il faut les choisir tous les deux par cadre ; un clic simple ou un cadre vide ne suffit pas. Le cadre sélectionne les formes et les images ; choisissez les traits et le texte par clic.',
         'Empieza en blanco arriba a la izquierda, rodea ambos rectángulos con un marco y suelta. Debes seleccionar los dos por marco; un clic o un marco vacío no basta. El marco selecciona formas e imágenes; selecciona trazos y texto con un clic.',
         'Beginnen Sie im freien Bereich links oben, ziehen Sie einen Rahmen um beide Rechtecke und lassen Sie los. Beide müssen per Rahmen gewählt sein; ein Einzelklick oder leerer Rahmen genügt nicht. Der Rahmen wählt Formen und Bilder; Striche und Text wählen Sie durch Klick.',
         'Начните с пустого места слева сверху, охватите рамкой оба прямоугольника и отпустите кнопку. Нужно выбрать рамкой оба; одного щелчка или пустой рамки недостаточно. Рамка выбирает фигуры и изображения; штрихи и текст выбирайте щелчком.',
         '왼쪽 위 빈 곳에서 두 사각형을 포함하는 선택 테두리를 끌고 놓으세요. 둘 다 영역 선택해야 하며 한 번의 클릭이나 빈 선택 영역은 인정되지 않습니다. 영역 선택은 도형과 이미지에 적용되고 선과 텍스트는 클릭하여 선택합니다.',
         '左上の空白から二つの矩形を囲む選択枠をドラッグして離します。両方を範囲選択する必要があり、一つのクリックや空の枠では完了しません。範囲選択は図形と画像が対象です。線や文字はクリックして選択します。')),
    'copy': (
        ('复制选中的两个样例', 'Copy both selected samples', 'Copier les deux exemples choisis', 'Copia los dos ejemplos seleccionados', 'Beide ausgewählten Beispiele kopieren', 'Скопируйте оба выбранных примера', '선택된 두 예제 복사', '選択した二つのサンプルを複製'),
        ('点击选中面板的“复”（复制），生成两个新副本。软件会自动选中副本；原件仍保留，位置会按可用空间安排。',
         'Select “Copy” on the selection panel to create two new copies. The copies become selected, the originals stay, and their placement follows the available space.',
         'Cliquez sur « Copie » dans le panneau de sélection pour créer deux copies. Elles sont automatiquement choisies, les originaux restent et la position dépend de l’espace disponible.',
         'Pulsa «Copia» en el panel de selección para crear dos copias. Se seleccionan las copias, los originales permanecen y la posición depende del espacio disponible.',
         'Wählen Sie „Kopie“ im Auswahlbereich, um zwei Kopien zu erzeugen. Die Kopien sind danach ausgewählt; die Originale bleiben und die Position richtet sich nach dem freien Platz.',
         'Нажмите «Копия» на панели выбора, чтобы создать две копии. Они будут выбраны автоматически; оригиналы сохранятся, а размещение зависит от свободного места.',
         '선택 패널의 “복사”를 눌러 새 복사본 두 개를 만드세요. 복사본이 자동 선택되고 원본은 남으며 위치는 사용 가능한 공간에 따라 정해집니다.',
         '選択パネルの「複製」で二つのコピーを作ります。コピーが自動選択され、元は残り、配置は空き領域に応じて決まります。')),
    'delete': (
        ('删除自动选中的副本', 'Delete the selected copies', 'Supprimer les copies sélectionnées', 'Borra las copias seleccionadas', 'Ausgewählte Kopien löschen', 'Удалите выбранные копии', '자동 선택된 복사본 삭제', '自動選択されたコピーを削除'),
        ('保持副本选中，点击“删”（删除），实际移除两个副本。两个原图形应继续保留；这次删除可以撤销。',
         'Keep the copies selected and select “Del” to remove both. The two original shapes stay, and this deletion can be undone.',
         'Gardez les copies choisies et cliquez sur « Suppr » pour les retirer. Les deux formes initiales restent ; cette suppression peut être annulée.',
         'Mantén seleccionadas las copias y pulsa «Borrar» para quitar ambas. Las dos formas originales permanecen y puedes deshacer este borrado.',
         'Lassen Sie die Kopien ausgewählt und wählen Sie „Löschen“, um beide zu entfernen. Die Originale bleiben; das Löschen lässt sich rückgängig machen.',
         'Оставьте копии выбранными и нажмите «Удал.», чтобы удалить обе. Две исходные фигуры останутся; удаление можно отменить.',
         '복사본을 선택한 상태로 “삭제”를 눌러 두 복사본을 지우세요. 원래 두 도형은 남으며 이 삭제는 실행 취소할 수 있습니다.',
         'コピーを選択したまま「削除」で両方を消します。元の二つの図形は残り、この削除は元に戻せます。')),
    'undo': (
        ('撤销删除并恢复副本', 'Undo deletion to restore copies', 'Annuler pour rétablir les copies', 'Deshaz el borrado y restaura las copias', 'Löschen rückgängig machen', 'Отмените удаление копий', '삭제 실행 취소로 복사본 복원', '削除を元に戻してコピーを復元'),
        ('点击“撤销”，恢复刚删除的两个副本。这里只恢复内容，不要求重新选中副本；空历史或没有内容变化不算完成。',
         'Select “Undo” to restore the two deleted copies. Restoring content is enough; no reselection is required, and empty history or unchanged content does not complete this step.',
         'Cliquez sur « Annuler » pour rétablir les deux copies supprimées. Il suffit de restaurer le contenu ; une nouvelle sélection n’est pas requise, et un historique vide ou un contenu inchangé ne termine pas l’étape.',
         'Pulsa «Deshacer» para restaurar las dos copias borradas. Basta restaurar el contenido, sin volver a seleccionarlas; el historial vacío o sin cambios no completa el paso.',
         'Wählen Sie „Rückgängig“, um beide Kopien wiederherzustellen. Erneutes Auswählen ist nicht nötig; eine leere Historie oder unveränderter Inhalt schließt den Schritt nicht ab.',
         'Нажмите «Отменить», чтобы восстановить обе удалённые копии. Повторно выбирать их не нужно; пустая история или отсутствие изменения не завершает шаг.',
         '“실행 취소”를 눌러 삭제한 두 복사본을 복원하세요. 다시 선택할 필요는 없으며 빈 기록이나 내용 변화가 없으면 완료되지 않습니다.',
         '「元に戻す」で削除した二つのコピーを復元します。再選択は不要です。空の履歴や内容が変わらない操作では完了しません。')),
    'done': (
        ('确认本章完成', 'Confirm chapter completion', 'Confirmer la fin du chapitre', 'Confirma el capítulo', 'Kapitelabschluss bestätigen', 'Подтвердите завершение главы', '장 완료 확인', '章の完了を確認'),
        ('完成本章必做操作后，点击“下一步”确认。可在教学中心换章，或点击“退出教学”回原工作；跳过不计完成。',
         'After the required actions, select “Next step” to confirm. Change chapters in the tutorial center or select “Exit tutorial” to return to your work; skipping is not completion.',
         'Après les actions requises, cliquez sur « Étape suivante » pour confirmer. Changez de chapitre dans le centre ou quittez le tutoriel pour retrouver votre travail ; passer ne compte pas comme terminer.',
         'Tras las acciones obligatorias, pulsa «Paso siguiente» para confirmar. Cambia de capítulo en el centro o sal del tutorial para volver a tu trabajo; omitir no cuenta como completar.',
         'Bestätigen Sie nach den erforderlichen Aktionen mit „Nächster Schritt“. Wechseln Sie im Tutorialcenter das Kapitel oder beenden Sie es zur Rückkehr; Überspringen zählt nicht als Abschluss.',
         'После обязательных действий нажмите «Следующий шаг» для подтверждения. Смените главу в центре обучения или выйдите, чтобы вернуться к работе; пропуск не считается завершением.',
         '필수 작업을 마친 뒤 “다음 단계”로 확인하세요. 교육 센터에서 장을 바꾸거나 교육을 종료하여 원래 작업으로 돌아갈 수 있으며 건너뛰기는 완료로 계산되지 않습니다.',
         '必要な操作の後に「次のステップ」で確認します。センターで章を変更するか、チュートリアルを終了して元の作業へ戻れます。スキップは完了に数えません。')),
}

for _chapter, _steps in {
    'select_move': ('intro', 'tool', 'select', 'move', 'done'),
    'transform': ('intro', 'tool', 'select', 'handles', 'scale', 'rotate', 'done'),
    'copy_delete': ('intro', 'tool', 'box', 'copy', 'delete', 'undo', 'done'),
}.items():
    for _step in _steps:
        _title, _body = _STEP_TEXT[_step]
        SELECTION_COPY['teaching_c04_' + _chapter + '_' + _step + '_title'] = _title
        SELECTION_COPY['teaching_c04_' + _chapter + '_' + _step + '_body'] = _body

del _chapter, _steps, _step, _title, _body
