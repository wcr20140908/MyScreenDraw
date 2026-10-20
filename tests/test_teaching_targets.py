# SPDX-License-Identifier: GPL-3.0-or-later
"""Semantic targets use isolated, real Qt trees, never the production panel."""
from __future__ import annotations

import gc
import os
import weakref
from collections.abc import Iterator

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QObject, QPoint, QRect, QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication, QMenu, QPushButton, QScrollArea, QVBoxLayout, QWidget, QWidgetAction,
)


def drain_events(app: QApplication) -> None:
    for _ in range(6):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def no_keyboard(monkeypatch: pytest.MonkeyPatch) -> None:
    import main

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail('Target tests must not create a production panel or keyboard hook')

    monkeypatch.setattr(main.keyboard, 'Listener', forbidden)
    monkeypatch.setattr(main.ControlPanel, '__init__', forbidden)


@pytest.fixture
def qt_app(no_keyboard: None) -> Iterator[QApplication]:
    app = QApplication.instance() or QApplication([])
    previous = {id(widget) for widget in app.topLevelWidgets()}
    yield app
    for widget in app.topLevelWidgets():
        if id(widget) not in previous and not sip.isdeleted(widget):
            widget.hide()
            widget.deleteLater()
    drain_events(app)


@pytest.fixture
def registry(qt_app: QApplication):
    from teaching.targets import TargetRegistry

    value = TargetRegistry()
    yield value
    value.close()
    value.deleteLater()
    drain_events(qt_app)


@pytest.fixture
def window(qt_app: QApplication) -> QWidget:
    host = QWidget()
    host.setGeometry(80, 70, 420, 260)
    host.show()
    drain_events(qt_app)
    return host


def make_button(parent: QWidget, x: int = 36, y: int = 32) -> QPushButton:
    button = QPushButton('Caption is not an ID', parent)
    button.setGeometry(x, y, 96, 28)
    button.show()
    return button


@pytest.fixture
def scroll_tree(window: QWidget, qt_app: QApplication):
    area = QScrollArea(window)
    area.setGeometry(15, 15, 190, 140)
    contents = QWidget()
    contents.resize(420, 640)
    button = make_button(contents, 310, 510)
    area.setWidget(contents)
    area.show()
    drain_events(qt_app)
    return area, contents, button


def test_registry_is_initially_inactive(registry, window, qt_app):
    calls = []
    button = make_button(window)
    registry.register('toolbar.pen', lambda: calls.append('resolve') or button)
    button.move(50, 40)
    window.resize(450, 300)
    drain_events(qt_app)
    assert isinstance(registry, QObject)
    assert calls == []
    assert registry.findChildren(QTimer) == []


def test_main_panel_like_icon_map_ignores_hidden_legacy_and_captions(registry, window):
    window.icon_buttons = {'pen': make_button(window)}
    window.legacy_pen = make_button(window, 140, 32)
    window.legacy_pen.hide()
    registry.register('toolbar.pen', lambda: window.icon_buttons.get('pen'))
    registry.register('legacy.pen', lambda: window.legacy_pen)
    window.icon_buttons['pen'].setText('Different translated caption')
    assert registry.resolve('toolbar.pen') is window.icon_buttons['pen']
    assert registry.resolve('legacy.pen') is None
    assert registry.global_rect('legacy.pen') is None
    assert not registry.reveal('legacy.pen')
    assert window.legacy_pen.isHidden()


def test_unknown_targets_have_no_widget_rect_or_reveal(registry):
    assert registry.resolve('missing.target') is None
    assert registry.global_rect('missing.target') is None
    assert not registry.reveal('missing.target')


def test_duplicate_ids_are_rejected_without_replacing_resolver(registry, window):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    with pytest.raises(ValueError, match='duplicate'):
        registry.register('toolbar.pen', lambda: None)
    assert registry.resolve('toolbar.pen') is button


@pytest.mark.parametrize('target_id', ['', 'translated caption', '../pen', 'a' * 129, None, 123])
def test_registration_uses_semantic_id_validation(registry, target_id):
    with pytest.raises(ValueError, match='invalid'):
        registry.register(target_id, lambda: None)


@pytest.mark.parametrize('method', ['resolve', 'reveal', 'global_rect', 'watch'])
def test_all_target_lookups_validate_semantic_ids(registry, method):
    with pytest.raises(ValueError, match='invalid'):
        if method == 'watch':
            registry.watch(['translated caption'], lambda: None)
        else:
            getattr(registry, method)('translated caption')


@pytest.mark.parametrize('resolver,reveal', [(None, None), (True, None), (lambda: None, True)])
def test_registration_rejects_noncallables(registry, resolver, reveal):
    with pytest.raises(TypeError):
        registry.register('toolbar.pen', resolver, reveal)


@pytest.mark.parametrize('hidden', ['target', 'ancestor'])
def test_hidden_target_or_ancestor_cannot_resolve(registry, window, hidden):
    parent = QWidget(window)
    parent.setGeometry(10, 10, 250, 100)
    parent.show()
    button = make_button(parent)
    registry.register('toolbar.pen', lambda: button)
    (button if hidden == 'target' else parent).hide()
    assert registry.resolve('toolbar.pen') is None
    assert registry.global_rect('toolbar.pen') is None


@pytest.mark.parametrize('candidate', [None, QObject(), object()])
def test_nonwidgets_are_not_targets(registry, candidate):
    registry.register('toolbar.pen', lambda: candidate)
    assert registry.resolve('toolbar.pen') is None
    assert registry.global_rect('toolbar.pen') is None
    assert not registry.reveal('toolbar.pen')


def test_sip_deleted_target_is_safe_even_if_resolver_keeps_wrapper(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    button.deleteLater()
    drain_events(qt_app)
    assert sip.isdeleted(button)
    assert registry.resolve('toolbar.pen') is None
    assert registry.global_rect('toolbar.pen') is None
    assert not registry.reveal('toolbar.pen')


def test_resolver_for_deleted_qt_owner_is_safe(registry):
    def stale_owner():
        raise RuntimeError('wrapped C/C++ object has been deleted')

    registry.register('toolbar.pen', stale_owner)
    assert registry.resolve('toolbar.pen') is None
    assert not registry.reveal('toolbar.pen')


def test_global_rect_maps_nested_widget_to_desktop_coordinates(registry, window):
    parent = QWidget(window)
    parent.setGeometry(20, 30, 250, 100)
    parent.show()
    button = make_button(parent, 12, 16)
    registry.register('toolbar.pen', lambda: button)
    expected = QRect(window.mapToGlobal(QPoint(32, 46)), button.size())
    assert registry.global_rect('toolbar.pen') == expected


def test_reveal_without_callback_does_not_show_arbitrary_hidden_controls(registry, window):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    assert registry.reveal('toolbar.pen')
    button.hide()
    assert not registry.reveal('toolbar.pen')
    assert button.isHidden()


def test_controlled_menu_reveal_re_resolves_target(registry, window, qt_app):
    menu = QMenu(window)
    action = QWidgetAction(menu)
    button = QPushButton('No caption lookup')
    action.setDefaultWidget(button)
    menu.addAction(action)
    calls = []

    def resolver():
        calls.append(menu.isVisible())
        return button if menu.isVisible() else None

    registry.register('file.export', resolver, lambda: menu.popup(window.mapToGlobal(QPoint(10, 10))))
    assert registry.resolve('file.export') is None
    assert registry.reveal('file.export')
    assert registry.resolve('file.export') is button
    assert calls[0] is False and calls[-1] is True
    menu.hide()
    drain_events(qt_app)
    assert registry.resolve('file.export') is None


def test_scroll_reveal_ensures_visibility_before_final_resolution(registry, scroll_tree):
    area, contents, button = scroll_tree
    positions = []

    def resolver():
        positions.append((area.horizontalScrollBar().value(), area.verticalScrollBar().value()))
        return button

    registry.register('settings.bottom', resolver)
    assert not area.viewport().rect().intersects(QRect(button.mapTo(area.viewport(), QPoint()), button.size()))
    assert registry.reveal('settings.bottom')
    assert positions[-1][0] > 0 and positions[-1][1] > 0
    assert area.viewport().rect().contains(QRect(button.mapTo(area.viewport(), QPoint()), button.size()))
    assert registry.resolve('settings.bottom') is button


def test_reveal_callback_can_rebuild_target(registry, window):
    holder = {'button': None}

    def reveal():
        holder['button'] = make_button(window)

    registry.register('toolbar.pen', lambda: holder['button'], reveal)
    assert registry.reveal('toolbar.pen')
    assert registry.resolve('toolbar.pen') is holder['button']


def test_failed_reveal_cannot_claim_a_visible_target(registry):
    def reveal():
        raise RuntimeError('menu owner was deleted')

    registry.register('file.export', lambda: None, reveal)
    assert not registry.reveal('file.export')


def test_watch_initial_notification_is_deferred_and_resolves_latest_target(registry, window, qt_app):
    holder = {'button': make_button(window)}
    replacement = make_button(window, 180, 90)
    drain_events(qt_app)
    registry.register('toolbar.pen', lambda: holder['button'])
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    assert observed == []
    holder['button'] = replacement
    drain_events(qt_app)
    assert observed == [QRect(window.mapToGlobal(QPoint(180, 90)), holder['button'].size())]


def test_watch_tracks_movable_top_level_parent(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    before = observed[-1]
    observed.clear()
    window.move(window.pos() + QPoint(25, 37))
    drain_events(qt_app)
    assert observed == [before.translated(25, 37)]


@pytest.mark.parametrize('change', ['move', 'resize', 'hide', 'ancestor-hide'])
def test_watch_tracks_target_geometry_and_visibility(registry, window, qt_app, change):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    before = observed[-1]
    observed.clear()
    if change == 'move':
        button.move(button.pos() + QPoint(9, 11))
        expected = before.translated(9, 11)
    elif change == 'resize':
        button.resize(120, 42)
        expected = QRect(before.topLeft(), button.size())
    else:
        (button if change == 'hide' else window).hide()
        expected = None
    drain_events(qt_app)
    assert observed == [expected]


def test_hidden_candidate_is_watched_but_never_selected_until_show(registry, window, qt_app):
    button = make_button(window)
    button.hide()
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.resolve('toolbar.pen') is button))
    drain_events(qt_app)
    assert observed == [False]
    button.show()
    drain_events(qt_app)
    assert observed == [False, True]


def test_watch_tracks_layout_changes(registry, window, qt_app):
    layout = QVBoxLayout(window)
    button = QPushButton('Target')
    layout.addWidget(button)
    drain_events(qt_app)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    before = observed[-1]
    observed.clear()
    layout.setContentsMargins(45, 25, 10, 10)
    drain_events(qt_app)
    assert observed and observed[-1] != before
    assert observed[-1] == QRect(button.mapToGlobal(QPoint()), button.size())


def test_watch_scrolls_and_disconnects_only_its_own_scroll_signals(registry, scroll_tree, qt_app):
    area, contents, button = scroll_tree
    horizontal, vertical = area.horizontalScrollBar(), area.verticalScrollBar()
    other = []
    vertical.valueChanged.connect(other.append)
    baseline = (horizontal.receivers(horizontal.valueChanged), vertical.receivers(vertical.valueChanged))
    registry.register('settings.bottom', lambda: button)
    observed = []
    registry.watch(['settings.bottom'], lambda: observed.append(registry.global_rect('settings.bottom')))
    drain_events(qt_app)
    before = observed[-1]
    observed.clear()
    horizontal.setValue(20)
    vertical.setValue(60)
    drain_events(qt_app)
    assert observed == [before.translated(-20, -60)]
    registry.unwatch()
    assert (horizontal.receivers(horizontal.valueChanged), vertical.receivers(vertical.valueChanged)) == baseline
    vertical.setValue(70)
    drain_events(qt_app)
    assert other[-1] == 70
    assert len(observed) == 1


def test_multiple_active_ids_and_iterators_are_supported(registry, window, qt_app):
    first, second = make_button(window), make_button(window, 180, 80)
    registry.register('toolbar.pen', lambda: first)
    registry.register('toolbar.eraser', lambda: second)
    observed = []
    registry.watch(iter(['toolbar.pen', 'toolbar.eraser', 'missing.target', 'toolbar.pen']),
                   lambda: observed.append((registry.global_rect('toolbar.pen'), registry.global_rect('toolbar.eraser'))))
    drain_events(qt_app)
    observed.clear()
    first.move(40, 50)
    second.resize(110, 32)
    drain_events(qt_app)
    assert observed == [(QRect(first.mapToGlobal(QPoint()), first.size()),
                         QRect(second.mapToGlobal(QPoint()), second.size()))]


def test_unrelated_windows_and_inactive_resolvers_are_not_watched(registry, window, qt_app):
    active = make_button(window)
    other_host = QWidget()
    other_host.setGeometry(500, 100, 200, 150)
    inactive = make_button(other_host)
    other_host.show()
    drain_events(qt_app)
    resolved = []
    registry.register('toolbar.pen', lambda: active)
    registry.register('inactive.pen', lambda: resolved.append(True) or inactive)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(True))
    drain_events(qt_app)
    observed.clear()
    other_host.move(550, 150)
    inactive.resize(110, 40)
    drain_events(qt_app)
    assert observed == [] and resolved == []
    QTest.qWait(30)
    assert observed == [] and resolved == []


def test_watch_never_installs_app_global_filters_or_swallows_input(registry, window, qt_app, monkeypatch):
    def forbidden(*args):
        pytest.fail('No app-global filter is permitted')

    monkeypatch.setattr(QApplication, 'installEventFilter', forbidden)
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    clicked, observed = [], []
    button.clicked.connect(lambda: clicked.append(True))
    registry.watch(['toolbar.pen'], lambda: observed.append(True))
    drain_events(qt_app)
    observed.clear()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    drain_events(qt_app)
    assert clicked == [True]
    assert observed == []


def test_movement_resize_and_layout_burst_share_one_single_shot_timer(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    observed.clear()
    button.move(40, 50)
    button.resize(120, 36)
    window.move(window.pos() + QPoint(10, 10))
    QCoreApplication.sendEvent(window, QEvent(QEvent.Type.LayoutRequest))
    assert observed == []
    timers = registry.findChildren(QTimer)
    assert len(timers) == 1 and timers[0].isSingleShot() and timers[0].isActive()
    drain_events(qt_app)
    assert observed == [QRect(button.mapToGlobal(QPoint()), button.size())]
    assert not timers[0].isActive()
    QTest.qWait(30)
    assert len(observed) == 1


@pytest.mark.parametrize('signal', ['geometryChanged', 'availableGeometryChanged', 'virtualGeometryChanged',
                                   'logicalDotsPerInchChanged', 'physicalDotsPerInchChanged', 'screenChanged'])
def test_relevant_window_and_screen_signals_are_scoped_and_disconnected(registry, window, qt_app, signal):
    button = make_button(window)
    handle = window.windowHandle()
    screen = handle.screen()
    source = handle if signal == 'screenChanged' else screen
    bound_signal = getattr(source, signal)
    baseline = source.receivers(bound_signal)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    observed.clear()
    argument = screen if signal == 'screenChanged' else (96.0 if 'DotsPerInch' in signal else screen.geometry())
    bound_signal.emit(argument)
    drain_events(qt_app)
    assert observed == [QRect(button.mapToGlobal(QPoint()), button.size())]
    registry.unwatch()
    assert source.receivers(bound_signal) == baseline
    bound_signal.emit(argument)
    drain_events(qt_app)
    assert len(observed) == 1


def test_device_pixel_ratio_event_refreshes_target(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    observed.clear()
    QCoreApplication.sendEvent(window.windowHandle(), QEvent(QEvent.Type.DevicePixelRatioChange))
    drain_events(qt_app)
    assert observed == [QRect(button.mapToGlobal(QPoint()), button.size())]


def test_showing_initially_hidden_host_binds_its_new_window_handle(registry, qt_app):
    host = QWidget()
    button = make_button(host)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    assert observed == [None]
    host.show()
    drain_events(qt_app)
    assert observed[-1] == QRect(button.mapToGlobal(QPoint()), button.size())
    observed.clear()
    host.windowHandle().screenChanged.emit(host.windowHandle().screen())
    drain_events(qt_app)
    assert len(observed) == 1


def test_deletion_then_later_rebuild_refreshes_watches_from_surviving_host(registry, window, qt_app):
    old = make_button(window)
    holder = {'button': old}
    registry.register('toolbar.pen', lambda: holder['button'])
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    holder['button'] = None
    old.deleteLater()
    drain_events(qt_app)
    assert sip.isdeleted(old)
    assert observed[-1] is None
    new = make_button(window, 140, 90)
    holder['button'] = new
    drain_events(qt_app)
    assert observed[-1] == QRect(new.mapToGlobal(QPoint()), new.size())
    observed.clear()
    new.move(150, 100)
    drain_events(qt_app)
    assert observed == [QRect(new.mapToGlobal(QPoint()), new.size())]


def test_reparenting_refreshes_ancestors_and_detaches_old_host(registry, window, qt_app):
    button = make_button(window)
    other_host = QWidget()
    other_host.setGeometry(500, 100, 250, 160)
    other_host.show()
    drain_events(qt_app)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(registry.global_rect('toolbar.pen')))
    drain_events(qt_app)
    button.setParent(other_host)
    button.show()
    drain_events(qt_app)
    assert observed[-1] == QRect(button.mapToGlobal(QPoint()), button.size())
    observed.clear()
    window.move(90, 90)
    drain_events(qt_app)
    assert observed == []
    other_host.move(520, 120)
    drain_events(qt_app)
    assert observed == [QRect(button.mapToGlobal(QPoint()), button.size())]


def test_unwatch_cancels_pending_callback_and_releases_timer(registry, window, qt_app):
    button = make_button(window)
    baseline = window.receivers(window.destroyed)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(True))
    registry.unwatch()
    registry.unwatch()
    button.move(80, 90)
    drain_events(qt_app)
    assert observed == []
    assert registry.findChildren(QTimer) == []
    assert window.receivers(window.destroyed) == baseline
    assert registry.resolve('toolbar.pen') is button


def test_changing_watch_targets_removes_previous_scope_and_callback(registry, window, qt_app):
    first = make_button(window)
    other_host = QWidget()
    second = make_button(other_host)
    other_host.show()
    drain_events(qt_app)
    registry.register('toolbar.pen', lambda: first)
    registry.register('toolbar.eraser', lambda: second)
    old, new = [], []
    registry.watch(['toolbar.pen'], lambda: old.append(True))
    registry.watch(['toolbar.eraser'], lambda: new.append(True))
    drain_events(qt_app)
    assert old == [] and new == [True]
    new.clear()
    first.move(100, 80)
    drain_events(qt_app)
    assert new == []
    second.move(60, 60)
    drain_events(qt_app)
    assert new == [True]


def test_empty_watch_deactivates_registry(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(True))
    registry.watch([], lambda: observed.append(False))
    drain_events(qt_app)
    assert observed == [] and registry.findChildren(QTimer) == []


def test_callback_may_unwatch_itself(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button)
    observed = []

    def callback():
        observed.append(True)
        registry.unwatch()

    registry.watch(['toolbar.pen'], callback)
    drain_events(qt_app)
    button.move(60, 60)
    drain_events(qt_app)
    assert observed == [True]
    assert registry.findChildren(QTimer) == []


def test_tracking_does_not_keep_widgets_alive_with_weak_resolvers(registry, qt_app):
    host = QWidget()
    button = make_button(host)
    host.show()
    drain_events(qt_app)
    host_ref, button_ref = weakref.ref(host), weakref.ref(button)
    registry.register('toolbar.pen', button_ref)
    registry.watch(['toolbar.pen'], lambda: None)
    drain_events(qt_app)
    del button, host
    gc.collect()
    drain_events(qt_app)
    assert host_ref() is None and button_ref() is None
    assert registry.resolve('toolbar.pen') is None


def test_one_hundred_activate_cleanup_cycles_leave_no_filters_connections_or_timers(registry, window, qt_app):
    button = make_button(window)
    screen = window.windowHandle().screen()
    baseline = (window.receivers(window.destroyed), screen.receivers(screen.geometryChanged))
    registry.register('toolbar.pen', lambda: button)
    observed = []
    for _ in range(100):
        registry.watch(['toolbar.pen'], lambda: observed.append(True))
        drain_events(qt_app)
        registry.unwatch()
        drain_events(qt_app)
        assert registry.findChildren(QTimer) == []
        assert (window.receivers(window.destroyed), screen.receivers(screen.geometryChanged)) == baseline
    assert len(observed) == 100
    window.move(100, 100)
    drain_events(qt_app)
    assert len(observed) == 100


def test_one_hundred_closed_sessions_release_captured_windows_and_callbacks(qt_app):
    from teaching.targets import TargetRegistry

    retained_registries, references = [], []
    screen = qt_app.primaryScreen()
    baseline = screen.receivers(screen.geometryChanged)
    for _ in range(100):
        host = QWidget()
        button = make_button(host)
        host.show()
        drain_events(qt_app)
        value = TargetRegistry()
        value.register('toolbar.pen', lambda owner=host: owner.findChild(QPushButton), host.show)
        value.watch(['toolbar.pen'], lambda owner=host: None)
        drain_events(qt_app)
        references.extend((weakref.ref(host), weakref.ref(button)))
        value.close()
        value.close()
        retained_registries.append(value)
        del button, host
    gc.collect()
    drain_events(qt_app)
    assert all(reference() is None for reference in references)
    assert all(value.findChildren(QTimer) == [] for value in retained_registries)
    assert screen.receivers(screen.geometryChanged) == baseline
    for value in retained_registries:
        value.deleteLater()


def test_closed_registry_is_inert_and_cannot_be_reactivated(registry, window, qt_app):
    button = make_button(window)
    registry.register('toolbar.pen', lambda: button, button.show)
    observed = []
    registry.watch(['toolbar.pen'], lambda: observed.append(True))
    registry.close()
    drain_events(qt_app)
    assert observed == []
    assert registry.resolve('toolbar.pen') is None
    assert registry.global_rect('toolbar.pen') is None
    assert not registry.reveal('toolbar.pen')
    with pytest.raises(RuntimeError, match='closed'):
        registry.register('toolbar.eraser', lambda: button)
    with pytest.raises(RuntimeError, match='closed'):
        registry.watch(['toolbar.pen'], lambda: None)



def test_extra_resolver_surfaces_are_watched_without_registering_permanent_ids(registry, window, qt_app):
    calls = []
    registry.watch([], lambda: calls.append(True), extra_resolvers=(lambda: window,))
    drain_events(qt_app)
    calls.clear()
    window.hide()
    drain_events(qt_app)
    assert calls == [True]
    assert registry._entries == {}
    registry.unwatch()
    assert registry._on_change is None and registry._watched == {}
    assert registry._extra_resolvers == ()


def test_extra_resolver_validation_preserves_existing_watch(registry, window, qt_app):
    registry.register('host', lambda: window)
    callback = lambda: None
    registry.watch(['host'], callback)
    with pytest.raises(TypeError):
        registry.watch([], lambda: None, extra_resolvers=(None,))
    assert registry._on_change is callback


def test_reentrant_close_inside_initial_resolver_never_installs_watches(registry, window):
    def resolve():
        registry.close()
        return window
    registry.register('host', resolve)
    registry.watch(['host'], lambda: None)
    assert registry._timer is None and registry._watched == {}
    assert registry._on_change is None


def test_deferred_resolution_failure_reports_once_and_unwatches(registry, window, qt_app, monkeypatch):
    import sys
    broken, failures, uncaught = [False], [], []
    def resolve():
        if broken[0]:
            raise ValueError('synthetic delayed resolver failure')
        return window
    registry.register('host', resolve)
    registry.failed.connect(failures.append)
    registry.watch(['host'], lambda: None)
    drain_events(qt_app)
    monkeypatch.setattr(sys, 'excepthook', lambda *args: uncaught.append(args))
    broken[0] = True
    window.hide()
    drain_events(qt_app)
    assert failures == ['target_resolution_failed'] and uncaught == []
    assert registry._on_change is None and registry._watched == {}
