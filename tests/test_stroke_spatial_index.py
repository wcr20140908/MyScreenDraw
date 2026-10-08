# SPDX-License-Identifier: GPL-3.0-or-later
"""Spatial queries preserve paint order while excluding unrelated ink."""
import pytest
from PyQt6.QtCore import QLine,QRectF
from PyQt6.QtGui import QPen

from stroke_cache import StrokeGeometryCache


def sync(cache,segments):
    return cache.sync(segments,{'marker'},lambda segment:segment['pen'].widthF()/2)


def part(name,x,y,end_x=None):
    return {'id':name,'line':QLine(x,y,end_x if end_x is not None else x+10,y+10),'pen':QPen(),'marker':False}


def test_small_clip_queries_only_local_commands_in_original_order():
    cache=StrokeGeometryCache()
    segments=[part(str(i),i*180,0) for i in range(5000)]
    commands=sync(cache,segments)
    visible=list(cache.visible_commands(QRectF(350,0,40,30)))
    assert visible==[commands[2]]
    assert cache.query_candidates<10


def test_active_append_and_group_growth_are_added_to_spatial_query():
    cache=StrokeGeometryCache()
    segments=[dict(part('marker',0,0),marker=True)]
    commands=sync(cache,segments)
    segments.append(dict(part('marker',600,0),marker=True))
    sync(cache,segments)
    assert list(cache.visible_commands(QRectF(590,-5,40,30)))==[commands[0]]
    segments.append(part('new',700,0));sync(cache,segments)
    assert [command.segment['id'] for command in cache.visible_commands(QRectF(690,-5,40,30))]==['new']


def test_negative_coordinates_and_huge_paths_remain_visible_without_grid_explosion():
    cache=StrokeGeometryCache()
    commands=sync(cache,[part('negative',-400,-300),part('wide',-100000,0,100000)])
    assert list(cache.visible_commands(QRectF(-405,-305,30,30)))==[commands[0]]
    assert list(cache.visible_commands(QRectF(50000,-5,20,30)))==[commands[1]]
    assert cache.index_entries<300


def test_removed_and_replaced_lists_never_reuse_old_spatial_entries():
    cache=StrokeGeometryCache()
    segments=[part('old',0,0)]
    sync(cache,segments)
    segments[:]=[part('new',900,0)];sync(cache,segments)
    assert list(cache.visible_commands(QRectF(-5,-5,30,30)))==[]
    assert [command.segment['id'] for command in cache.visible_commands(QRectF(895,-5,30,30))]==['new']
