# -*- coding: utf-8 -*-
"""
validate_data.py - 游戏数据 JSON 校验模块

启动时调用 validate_all(data_root)，校验 data 目录下所有 JSON 文件的
结构与必填字段，返回错误列表（空列表表示全部通过）。
设计文档第三部分承诺：把运行时崩溃提前扼杀在编辑阶段。
"""
import json
import os
import glob
from typing import List


def _load(data_root: str, rel: str):
    with open(os.path.join(data_root, rel), encoding='utf-8') as f:
        return json.load(f)


def _load_raw(fp: str):
    with open(fp, encoding='utf-8') as f:
        return json.load(f)


def _check_condition(cond, label: str, errors: List[str]):
    """校验条件结构（logic + rules + 每个 rule 的 type）"""
    if not isinstance(cond, dict):
        errors.append(f"{label}: condition 不是对象")
        return
    if 'logic' not in cond or cond['logic'] not in ('AND', 'OR'):
        errors.append(f"{label}: condition 缺少合法 logic（AND/OR）")
    rules = cond.get('rules', [])
    if not isinstance(rules, list):
        errors.append(f"{label}: condition.rules 不是数组")
        return
    valid_types = {'stat', 'flag', 'counter', 'path_sequence', 'path_contains'}
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict) or 'type' not in rule:
            errors.append(f"{label}: condition.rules[{i}] 缺少 type")
            continue
        if rule['type'] not in valid_types:
            errors.append(f"{label}: condition.rules[{i}] 未知类型 {rule['type']}")


def validate_all(data_root: str) -> List[str]:
    """校验 data 目录下所有 JSON，返回错误列表（空列表表示全部通过）。"""
    errors: List[str] = []

    def _check(cond, msg):
        if not cond:
            errors.append(msg)

    # characters.json
    try:
        chars = _load(data_root, 'characters.json')
        for cid, c in chars.items():
            _check('name' in c, f"characters.json: 角色 [{cid}] 缺少 name")
            _check('base_stats' in c, f"characters.json: 角色 [{cid}] 缺少 base_stats")
            _check('start_relic' in c, f"characters.json: 角色 [{cid}] 缺少 start_relic")
    except Exception as e:
        errors.append(f"characters.json: {e}")

    # relics.json
    try:
        relics = _load(data_root, 'relics.json')
        for rid, r in relics.items():
            _check('name' in r, f"relics.json: 遗物 [{rid}] 缺少 name")
            _check('rarity' in r, f"relics.json: 遗物 [{rid}] 缺少 rarity")
    except Exception as e:
        errors.append(f"relics.json: {e}")

    # endings.json
    try:
        endings = _load(data_root, 'endings.json')
        _check(isinstance(endings, list), "endings.json: 应为数组")
        for i, e in enumerate(endings):
            eid = e.get('id', f'#{i}')
            _check('id' in e, f"endings.json: 第{i}个结局缺少 id")
            _check('name' in e, f"endings.json: 结局 [{eid}] 缺少 name")
            _check('condition' in e, f"endings.json: 结局 [{eid}] 缺少 condition")
            _check('text' in e, f"endings.json: 结局 [{eid}] 缺少 text")
            if 'condition' in e:
                _check_condition(e['condition'], f"endings.json 结局 [{eid}]", errors)
    except Exception as e:
        errors.append(f"endings.json: {e}")

    # labours.json
    try:
        labours = _load(data_root, 'labours.json')
        _check(isinstance(labours, dict), "labours.json: 应为对象")
        for pool, ids in labours.items():
            _check(isinstance(ids, list), f"labours.json: 池 [{pool}] 不是数组")
    except Exception as e:
        errors.append(f"labours.json: {e}")

    # random_events.json
    try:
        events = _load(data_root, 'random_events.json')
        _check(isinstance(events, list), "random_events.json: 应为数组")
        for ev in events:
            eid = ev.get('event_id', '?')
            _check('event_id' in ev, "random_events.json: 事件缺少 event_id")
            _check('title' in ev, f"random_events.json: 事件 [{eid}] 缺少 title")
            _check('text' in ev, f"random_events.json: 事件 [{eid}] 缺少 text")
            _check('options' in ev, f"random_events.json: 事件 [{eid}] 缺少 options")
    except Exception as e:
        errors.append(f"random_events.json: {e}")

    # chapters/*.json
    ch_dir = os.path.join(data_root, 'chapters')
    if os.path.isdir(ch_dir):
        for fp in sorted(glob.glob(os.path.join(ch_dir, '*.json'))):
            fname = os.path.basename(fp)
            try:
                evs = _load_raw(fp)
                _check(isinstance(evs, list), f"{fname}: 章节应为事件数组")
                for i, ev in enumerate(evs):
                    eid = ev.get('event_id', f'#{i}')
                    _check('event_id' in ev, f"{fname}: 第{i}个事件缺少 event_id")
                    _check('title' in ev, f"{fname}: 事件 [{eid}] 缺少 title")
                    _check('text' in ev, f"{fname}: 事件 [{eid}] 缺少 text")
                    _check('options' in ev, f"{fname}: 事件 [{eid}] 缺少 options")
                    for j, opt in enumerate(ev.get('options', [])):
                        _check('text' in opt,
                               f"{fname}: 事件 [{eid}] 选项{j} 缺少 text")
            except Exception as e:
                errors.append(f"{fname}: {e}")

    return errors


if __name__ == '__main__':
    import sys
    dr = sys.argv[1] if len(sys.argv) > 1 else 'data'
    errs = validate_all(dr)
    if errs:
        print("数据校验失败：")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    else:
        print("数据校验通过。")
