"""
运行所有单元测试

用法：
    cd D:/allin && python -m alloy.test.run_all
"""

import sys
import os

# 确保项目根目录（D:/allin）在路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from alloy.test.runner import TestRunner, ErrorType

# 导入所有测试
from alloy.test.test_core import (
    test_entity_create, test_entity_add_component, test_entity_has_component,
    test_entity_remove_component, test_entity_unique_id,
    test_world_create_entity, test_world_add_system, test_world_update,
    test_world_get_entity_by_eid, test_world_get_entity_by_id,
    test_world_remove_entity, test_world_entity_count,
    test_event_bus_subscribe, test_event_bus_emit, test_event_bus_unsubscribe,
    test_event_bus_once, test_event_bus_return_count, test_event_bus_clear,
    test_event_bus_has_listeners,
)
from alloy.test.test_world import (
    test_player_state_hp, test_player_state_hp_clamp, test_player_state_add_item,
    test_player_state_remove_item, test_player_state_flags, test_player_state_sanity,
    test_player_state_is_alive,
    test_game_state_create, test_game_state_flags, test_game_state_vars,
    test_game_state_serialization, test_game_state_record_event,
    test_item_create, test_item_effects, test_item_stats, test_item_is_weapon,
    test_character_create, test_character_stats_dict, test_character_hostile, test_character_hp,
    test_room_create, test_room_exits, test_room_items,
    test_map_graph_create, test_map_graph_add_node, test_map_graph_navigation,
    test_map_node_connections,
)
from alloy.test.test_systems import (
    test_inventory_create, test_inventory_add_item, test_inventory_get_item,
    test_inventory_remove_item, test_inventory_has, test_inventory_iter,
    test_inventory_capacity,
    test_puzzle_create, test_puzzle_verify,
    test_puzzle_system_create, test_puzzle_system_add, test_puzzle_system_get_nonexistent,
    test_save_load_create, test_save_load_save_and_load, test_save_load_list_slots,
)

from alloy.test.test_combat import (
    test_card_create, test_card_cost_property, test_card_serialization, test_card_repr,
    test_carddeck_create, test_carddeck_add_remove, test_carddeck_remove_all,
    test_carddeck_draw, test_carddeck_list_ids, test_carddeck_serialization,
    test_carddeck_contains,
    test_cardlibrary_register, test_cardlibrary_get_card, test_cardlibrary_get_nonexistent,
    test_cardlibrary_load_from_list,
    test_intent_create, test_intent_serialization,
    test_enemy_create, test_enemy_serialization,
    test_enemy_instance_create, test_enemy_instance_default_intent,
    test_enemy_instance_intent_cycle, test_enemy_instance_peek,
    test_enemy_instance_reset_intents,
    test_enemy_instance_take_damage, test_enemy_instance_take_damage_with_armor,
    test_enemy_instance_heal, test_enemy_instance_hp_percent, test_enemy_instance_alive,
    test_enemy_library_register, test_enemy_library_get_instance,
    test_enemy_library_list_bosses, test_enemy_library_load_from_list,
    test_combat_state_new, test_combat_play_card, test_combat_play_invalid_index,
    test_combat_victory, test_combat_defeat, test_combat_block_reduces_damage,
    test_combat_draw_hand, test_combat_shuffle_discard,
    test_combat_engine_start, test_combat_engine_play_card, test_combat_engine_end_combat,
)

from alloy.test.test_command import (
    test_command_result_ok, test_command_result_fail, test_command_result_to_dict,
    test_command_result_repr,
    test_parser_basic, test_parser_empty_input, test_parser_whitespace_only,
    test_parser_no_args, test_parser_multiple_args,
    test_parser_alias_q, test_parser_alias_exit, test_parser_alias_l,
    test_parser_alias_direction, test_parser_direction_with_modifier,
    test_parser_case_insensitive, test_parser_unknown_command,
    test_parser_add_alias, test_parser_remove_alias, test_parser_get_alias,
    test_parser_aliases_property, test_parser_parse_with_raw, test_parser_is_quit,
    test_parser_custom_aliases,
    test_handler_register_and_execute, test_handler_unknown_command,
    test_handler_str_return, test_handler_none_return, test_handler_command_result_return,
    test_handler_exception_handling, test_handler_context,
    test_handler_get_context, test_handler_clear_context,
    test_handler_unregister, test_handler_case_insensitive,
    test_handler_get_all_commands, test_handler_last_result, test_handler_result_history,
)

from alloy.test.test_mod_loader import (
    test_card_library_load_json_file, test_card_library_load_json_dir,
    test_card_library_load_wrapped_json, test_card_library_from_json,
    test_enemy_library_load_json_file, test_enemy_library_load_wrapped_json,
    test_portal_def, test_mechanism_def, test_map_def, test_mod_manifest,
    test_mod_manager_discover, test_mod_manager_empty_mods_dir,
    test_mod_manager_nonexistent_mods_dir, test_mod_manager_list_maps,
    test_mod_manager_find_data_dirs, test_mod_manager_get_nonexistent_mod,
)

from alloy.test.test_render import (
    test_map_data_from_string, test_map_data_empty, test_map_data_get_set,
    test_map_data_empty_string, test_map_data_uneven_lines,
    test_renderer_init, test_renderer_draw_text, test_renderer_draw_centered_text,
    test_renderer_draw_grid, test_renderer_draw_rect, test_renderer_draw_progress_bar,
    test_renderer_draw_progress_bar_zero_total,
    test_renderer_hline, test_renderer_vline,
    test_renderer_clear, test_renderer_resize,
    test_colorize, test_colorize_no_color, test_colorize_bold,
    test_strip_ansi, test_strip_ansi_plain_text,
    test_ansi_foreground_map, test_ansi_background_map, test_char_color_map,
    test_solid_color, test_solid_color_tuple,
    test_hsv_flow_color, test_hsv_flow_color_custom,
    test_energy_color, test_rainbow_color, test_rainbow_color_reset,
    test_formula_engine_import,
)

from alloy.test.test_audio import (
    test_note_to_freq_a4, test_note_to_freq_a5, test_note_to_freq_a3,
    test_note_to_freq_c4, test_note_to_freq_c5,
    test_note_to_freq_sharp, test_note_to_freq_flat,
    test_note_to_freq_underscore, test_note_to_freq_with_spaces,
    test_note_to_freq_custom_a4,
    test_note_to_freq_invalid, test_note_to_freq_invalid_no_octave,
    test_note_to_freq_octave_range,
    test_synth_voice_default, test_synth_voice_custom,
    test_adsr_params_default, test_adsr_params_custom,
    test_oscillator_sine, test_oscillator_saw, test_oscillator_square,
    test_oscillator_triangle,
    test_oscillator_noise_white, test_oscillator_noise_pink, test_oscillator_noise_brown,
    test_make_envelope_percussive, test_make_envelope_pad,
    test_make_envelope_pluck, test_make_envelope_swell, test_make_envelope_reverse,
    test_make_envelope_with_adsr,
    test_synthesize_voice_basic, test_synthesize_voice_with_harmonics,
    test_synthesize_voice_with_vibrato, test_synthesize_voice_with_detune,
    test_music_pattern_create, test_music_pattern_defaults,
    test_generate_music_wav_no_numpy,
)

from alloy.test.test_ai import (
    test_option_dataclass, test_scene_dataclass,
    test_game_state_create, test_game_state_serialization,
    test_eval_none_conditions, test_eval_empty_list, test_eval_empty_dict,
    test_eval_string_numeric_gte, test_eval_string_numeric_lte,
    test_eval_string_numeric_gt, test_eval_string_numeric_lt,
    test_eval_string_numeric_eq, test_eval_string_numeric_ne,
    test_eval_string_has_item, test_eval_string_not_has_item,
    test_eval_dict_conditions, test_eval_dict_has_item,
    test_eval_dict_suffix_ops, test_eval_dict_flag_has,
    test_eval_dict_no_suffix, test_eval_list_conditions,
    test_eval_unknown_attribute,
    test_narrative_engine_create, test_narrative_engine_state,
    test_dialogue_engine_create,
    test_dialogue_empty_input, test_dialogue_whitespace_input,
    test_dialogue_greeting, test_dialogue_thanks, test_dialogue_goodbye,
    test_dialogue_learn_and_recall, test_dialogue_learn_list,
    test_dialogue_forget, test_dialogue_custom_rules,
    test_dialogue_fallback, test_dialogue_safety_filter,
    test_match_result_create, test_match_result_empty,
    test_match_result_zero_confidence,
    test_generation_config_default,
    test_content_generator_create, test_content_generator_fallback,
)

from alloy.test.test_decision import (
    test_fsm_transition, test_fsm_invalid_event, test_fsm_factory_returns_fsm,
    test_fsm_internal_transition,
    test_hsm_nested_initial, test_hsm_transition_into_substate,
    test_hsm_internal_reset,
    test_bt_selector_high_load, test_bt_selector_normal, test_bt_sequence_fault,
    test_bt_inverter,
    test_dt_vip_urgent, test_dt_normal_low,
    test_fd_quadratic, test_state_diff_changed, test_reactive_tracker_subscribe,
    test_brain_component_tick, test_brain_event_bus_hook,
    test_fixed_loop_steps, test_fixed_loop_clamp,
    test_loader_default_config, test_loader_from_dict, test_loader_build_all_specs,
)

from alloy.test.test_font import (
    test_get_local_fonts_dir,
    test_discover_local_fonts_finds_bundled,
    test_list_local_fonts_nonempty,
    test_get_default_local_font_name,
    test_load_local_font_returns_pygame_font,
    test_load_local_font_by_name,
    test_load_local_font_renders_cjk,
    test_load_local_font_cache,
    test_load_local_font_missing_name_none,
    test_load_cjk_font_local_first,
    test_load_cjk_font_by_name,
    test_load_cjk_font_env_var,
    test_default_font_stable_with_extra_registered_fonts,
    test_load_local_tk_font_returns_or_none,
    test_load_cjk_tk_font_local_first,
    test_register_local_font_adds_alias,
    test_list_available_cjk_fonts_includes_local,
    test_clear_font_cache_resets,
)

from alloy.test.test_pathfinding import (
    test_grid_astar_basic, test_grid_astar_goal_in_wall_returns_none,
    test_grid_astar_enclosed_returns_none, test_grid_astar_out_of_bounds_returns_none,
    test_grid_astar_diagonal, test_grid_astar_no_diagonal_longer,
    test_graph_bfs, test_graph_dijkstra_weighted, test_graph_astar,
    test_graph_unreachable_returns_none, test_graph_same_node,
    test_graph_locked_skipped_when_not_ignored,
)

from alloy.test.test_serializable import (
    test_nested_dataclass_roundtrip, test_nested_list_empty,
    test_nested_dataclass_explicit_none_preserved,
)

from alloy.test.test_data_library import (
    test_data_library_registers_id_zero,
    test_json_loader_returns_independent_copies,
)

from alloy.test.test_world_log import (
    test_worldlog_append_increments_seq,
    test_worldlog_entries_in_order,
    test_worldlog_entries_since,
    test_worldlog_len,
    test_worldlog_projection_folds_events,
    test_worldlog_projection_unknown_key_raises,
    test_worldlog_rebuild_projection,
    test_worldlog_track_bridges_bus_events,
    test_worldlog_save_load_roundtrip,
    test_worldlog_deterministic_same_seed,
    test_worldlog_deterministic_diff_seed,
    test_worldlog_snapshot_rebuild_equals_direct,
    test_engine_provides_log_service,
    test_engine_unload_log,
    test_saveload_snapshot_log_roundtrip,
    test_worldlog_audit_summary,
)

from alloy.test.test_context import (
    test_context_provide_get,
    test_context_get_missing_raises,
    test_context_get_default,
    test_context_duplicate_provide_raises,
    test_context_replace_provides_new,
    test_context_effect_dispose_reverse_order,
    test_context_dispose_idempotent,
    test_context_child_lookup_parent,
    test_context_child_own_service_shadows_parent,
    test_context_child_dispose_keeps_parent,
    test_context_unload_runs_disposer_and_removes,
    test_context_unload_missing_returns_false,
    test_context_install_plugin,
    test_context_install_plugin_missing_dep_raises,
    test_context_install_apply_returns_disposer,
    test_engine_add_core_provides_services,
    test_engine_add_systems_get,
    test_engine_add_idempotent,
    test_engine_mount_plugin_provides_service,
    test_engine_unload_runs_disposer,
    test_engine_shutdown_then_readd,
    test_eventbus_waterfall_transform,
    test_eventbus_waterfall_short_circuit,
    test_eventbus_waterfall_no_listeners_passthrough,
    test_eventbus_serial_short_circuit,
    test_eventbus_serial_all_none_returns_none,
)


all_tests = [
    # core (19)
    test_entity_create, test_entity_add_component, test_entity_has_component,
    test_entity_remove_component, test_entity_unique_id,
    test_world_create_entity, test_world_add_system, test_world_update,
    test_world_get_entity_by_eid, test_world_get_entity_by_id,
    test_world_remove_entity, test_world_entity_count,
    test_event_bus_subscribe, test_event_bus_emit, test_event_bus_unsubscribe,
    test_event_bus_once, test_event_bus_return_count, test_event_bus_clear,
    test_event_bus_has_listeners,
    # world (27)
    test_player_state_hp, test_player_state_hp_clamp, test_player_state_add_item,
    test_player_state_remove_item, test_player_state_flags, test_player_state_sanity,
    test_player_state_is_alive,
    test_game_state_create, test_game_state_flags, test_game_state_vars,
    test_game_state_serialization, test_game_state_record_event,
    test_item_create, test_item_effects, test_item_stats, test_item_is_weapon,
    test_character_create, test_character_stats_dict, test_character_hostile, test_character_hp,
    test_room_create, test_room_exits, test_room_items,
    test_map_graph_create, test_map_graph_add_node, test_map_graph_navigation,
    test_map_node_connections,
    # systems (15)
    test_inventory_create, test_inventory_add_item, test_inventory_get_item,
    test_inventory_remove_item, test_inventory_has, test_inventory_iter,
    test_inventory_capacity,
    test_puzzle_create, test_puzzle_verify,
    test_puzzle_system_create, test_puzzle_system_add, test_puzzle_system_get_nonexistent,
    test_save_load_create, test_save_load_save_and_load, test_save_load_list_slots,
    # combat (35)
    test_card_create, test_card_cost_property, test_card_serialization, test_card_repr,
    test_carddeck_create, test_carddeck_add_remove, test_carddeck_remove_all,
    test_carddeck_draw, test_carddeck_list_ids, test_carddeck_serialization,
    test_carddeck_contains,
    test_cardlibrary_register, test_cardlibrary_get_card, test_cardlibrary_get_nonexistent,
    test_cardlibrary_load_from_list,
    test_intent_create, test_intent_serialization,
    test_enemy_create, test_enemy_serialization,
    test_enemy_instance_create, test_enemy_instance_default_intent,
    test_enemy_instance_intent_cycle, test_enemy_instance_peek,
    test_enemy_instance_reset_intents,
    test_enemy_instance_take_damage, test_enemy_instance_take_damage_with_armor,
    test_enemy_instance_heal, test_enemy_instance_hp_percent, test_enemy_instance_alive,
    test_enemy_library_register, test_enemy_library_get_instance,
    test_enemy_library_list_bosses, test_enemy_library_load_from_list,
    test_combat_state_new, test_combat_play_card, test_combat_play_invalid_index,
    test_combat_victory, test_combat_defeat, test_combat_block_reduces_damage,
    test_combat_draw_hand, test_combat_shuffle_discard,
    test_combat_engine_start, test_combat_engine_play_card, test_combat_engine_end_combat,
    # command (31)
    test_command_result_ok, test_command_result_fail, test_command_result_to_dict,
    test_command_result_repr,
    test_parser_basic, test_parser_empty_input, test_parser_whitespace_only,
    test_parser_no_args, test_parser_multiple_args,
    test_parser_alias_q, test_parser_alias_exit, test_parser_alias_l,
    test_parser_alias_direction, test_parser_direction_with_modifier,
    test_parser_case_insensitive, test_parser_unknown_command,
    test_parser_add_alias, test_parser_remove_alias, test_parser_get_alias,
    test_parser_aliases_property, test_parser_parse_with_raw, test_parser_is_quit,
    test_parser_custom_aliases,
    test_handler_register_and_execute, test_handler_unknown_command,
    test_handler_str_return, test_handler_none_return, test_handler_command_result_return,
    test_handler_exception_handling, test_handler_context,
    test_handler_get_context, test_handler_clear_context,
    test_handler_unregister, test_handler_case_insensitive,
    test_handler_get_all_commands, test_handler_last_result, test_handler_result_history,
    # mod_loader (16) — 数据驱动链路
    test_card_library_load_json_file, test_card_library_load_json_dir,
    test_card_library_load_wrapped_json, test_card_library_from_json,
    test_enemy_library_load_json_file, test_enemy_library_load_wrapped_json,
    test_portal_def, test_mechanism_def, test_map_def, test_mod_manifest,
    test_mod_manager_discover, test_mod_manager_empty_mods_dir,
    test_mod_manager_nonexistent_mods_dir, test_mod_manager_list_maps,
    test_mod_manager_find_data_dirs, test_mod_manager_get_nonexistent_mod,
    # render (30) — 渲染层
    test_map_data_from_string, test_map_data_empty, test_map_data_get_set,
    test_map_data_empty_string, test_map_data_uneven_lines,
    test_renderer_init, test_renderer_draw_text, test_renderer_draw_centered_text,
    test_renderer_draw_grid, test_renderer_draw_rect, test_renderer_draw_progress_bar,
    test_renderer_draw_progress_bar_zero_total,
    test_renderer_hline, test_renderer_vline,
    test_renderer_clear, test_renderer_resize,
    test_colorize, test_colorize_no_color, test_colorize_bold,
    test_strip_ansi, test_strip_ansi_plain_text,
    test_ansi_foreground_map, test_ansi_background_map, test_char_color_map,
    test_solid_color, test_solid_color_tuple,
    test_hsv_flow_color, test_hsv_flow_color_custom,
    test_energy_color, test_rainbow_color, test_rainbow_color_reset,
    test_formula_engine_import,
    # audio (35) — 音频层
    test_note_to_freq_a4, test_note_to_freq_a5, test_note_to_freq_a3,
    test_note_to_freq_c4, test_note_to_freq_c5,
    test_note_to_freq_sharp, test_note_to_freq_flat,
    test_note_to_freq_underscore, test_note_to_freq_with_spaces,
    test_note_to_freq_custom_a4,
    test_note_to_freq_invalid, test_note_to_freq_invalid_no_octave,
    test_note_to_freq_octave_range,
    test_synth_voice_default, test_synth_voice_custom,
    test_adsr_params_default, test_adsr_params_custom,
    test_oscillator_sine, test_oscillator_saw, test_oscillator_square,
    test_oscillator_triangle,
    test_oscillator_noise_white, test_oscillator_noise_pink, test_oscillator_noise_brown,
    test_make_envelope_percussive, test_make_envelope_pad,
    test_make_envelope_pluck, test_make_envelope_swell, test_make_envelope_reverse,
    test_make_envelope_with_adsr,
    test_synthesize_voice_basic, test_synthesize_voice_with_harmonics,
    test_synthesize_voice_with_vibrato, test_synthesize_voice_with_detune,
    test_music_pattern_create, test_music_pattern_defaults,
    test_generate_music_wav_no_numpy,
    # ai (37) — 智能层
    test_option_dataclass, test_scene_dataclass,
    test_game_state_create, test_game_state_serialization,
    test_eval_none_conditions, test_eval_empty_list, test_eval_empty_dict,
    test_eval_string_numeric_gte, test_eval_string_numeric_lte,
    test_eval_string_numeric_gt, test_eval_string_numeric_lt,
    test_eval_string_numeric_eq, test_eval_string_numeric_ne,
    test_eval_string_has_item, test_eval_string_not_has_item,
    test_eval_dict_conditions, test_eval_dict_has_item,
    test_eval_dict_suffix_ops, test_eval_dict_flag_has,
    test_eval_dict_no_suffix, test_eval_list_conditions,
    test_eval_unknown_attribute,
    test_narrative_engine_create, test_narrative_engine_state,
    test_dialogue_engine_create,
    test_dialogue_empty_input, test_dialogue_whitespace_input,
    test_dialogue_greeting, test_dialogue_thanks, test_dialogue_goodbye,
    test_dialogue_learn_and_recall, test_dialogue_learn_list,
    test_dialogue_forget, test_dialogue_custom_rules,
    test_dialogue_fallback, test_dialogue_safety_filter,
    test_match_result_create, test_match_result_empty,
    test_match_result_zero_confidence,
    test_generation_config_default,
    test_content_generator_create, test_content_generator_fallback,
    # decision (28) — 决策/行为范式：状态机/行为树/决策树/差分引擎/脑/循环
    test_fsm_transition, test_fsm_invalid_event, test_fsm_factory_returns_fsm,
    test_fsm_internal_transition,
    test_hsm_nested_initial, test_hsm_transition_into_substate,
    test_hsm_internal_reset,
    test_bt_selector_high_load, test_bt_selector_normal, test_bt_sequence_fault,
    test_bt_inverter,
    test_dt_vip_urgent, test_dt_normal_low,
    test_fd_quadratic, test_state_diff_changed, test_reactive_tracker_subscribe,
    test_brain_component_tick, test_brain_event_bus_hook,
    test_fixed_loop_steps, test_fixed_loop_clamp,
    test_loader_default_config, test_loader_from_dict, test_loader_build_all_specs,
    # font (18) — 本地字体加载
    test_get_local_fonts_dir,
    test_discover_local_fonts_finds_bundled,
    test_list_local_fonts_nonempty,
    test_get_default_local_font_name,
    test_load_local_font_returns_pygame_font,
    test_load_local_font_by_name,
    test_load_local_font_renders_cjk,
    test_load_local_font_cache,
    test_load_local_font_missing_name_none,
    test_load_cjk_font_local_first,
    test_load_cjk_font_by_name,
    test_load_cjk_font_env_var,
    test_default_font_stable_with_extra_registered_fonts,
    test_load_local_tk_font_returns_or_none,
    test_load_cjk_tk_font_local_first,
    test_register_local_font_adds_alias,
    test_list_available_cjk_fonts_includes_local,
    test_clear_font_cache_resets,

    # pathfinding (12)
    test_grid_astar_basic, test_grid_astar_goal_in_wall_returns_none,
    test_grid_astar_enclosed_returns_none, test_grid_astar_out_of_bounds_returns_none,
    test_grid_astar_diagonal, test_grid_astar_no_diagonal_longer,
    test_graph_bfs, test_graph_dijkstra_weighted, test_graph_astar,
    test_graph_unreachable_returns_none, test_graph_same_node,
    test_graph_locked_skipped_when_not_ignored,

    # serializable (3)
    test_nested_dataclass_roundtrip, test_nested_list_empty,
    test_nested_dataclass_explicit_none_preserved,

    # data_library / json_loader (2)
    test_data_library_registers_id_zero,
    test_json_loader_returns_independent_copies,

    # context (26) — 可逆装配内核 / 插件协议 / GameEngine 兼容 / 分派模式
    test_context_provide_get,
    test_context_get_missing_raises,
    test_context_get_default,
    test_context_duplicate_provide_raises,
    test_context_replace_provides_new,
    test_context_effect_dispose_reverse_order,
    test_context_dispose_idempotent,
    test_context_child_lookup_parent,
    test_context_child_own_service_shadows_parent,
    test_context_child_dispose_keeps_parent,
    test_context_unload_runs_disposer_and_removes,
    test_context_unload_missing_returns_false,
    test_context_install_plugin,
    test_context_install_plugin_missing_dep_raises,
    test_context_install_apply_returns_disposer,
    test_engine_add_core_provides_services,
    test_engine_add_systems_get,
    test_engine_add_idempotent,
    test_engine_mount_plugin_provides_service,
    test_engine_unload_runs_disposer,
    test_engine_shutdown_then_readd,
    test_eventbus_waterfall_transform,
    test_eventbus_waterfall_short_circuit,
    test_eventbus_waterfall_no_listeners_passthrough,
    test_eventbus_serial_short_circuit,
    test_eventbus_serial_all_none_returns_none,

    # world_log (16) — 日志即事实源
    test_worldlog_append_increments_seq,
    test_worldlog_entries_in_order,
    test_worldlog_entries_since,
    test_worldlog_len,
    test_worldlog_projection_folds_events,
    test_worldlog_projection_unknown_key_raises,
    test_worldlog_rebuild_projection,
    test_worldlog_track_bridges_bus_events,
    test_worldlog_save_load_roundtrip,
    test_worldlog_deterministic_same_seed,
    test_worldlog_deterministic_diff_seed,
    test_worldlog_snapshot_rebuild_equals_direct,
    test_engine_provides_log_service,
    test_engine_unload_log,
    test_saveload_snapshot_log_roundtrip,
    test_worldlog_audit_summary,
]


def main() -> int:
    """运行全部单元测试。

    返回进程退出码：0 = 全部通过（忽略跳过），1 = 存在失败。
    供 pyproject [project.scripts] 的 allin-test 入口调用。
    """
    runner = TestRunner(timeout=5.0)

    print("=" * 60)
    print("  alloy 单元测试汇总")
    print("=" * 60)
    print()
    print(f"共 {len(all_tests)} 个测试")
    print()

    results = runner.run_tests(all_tests)

    passed = sum(1 for r in results if r.success)
    skipped = sum(1 for r in results if r.error_type == ErrorType.TEST_SKIP)
    failed = sum(
        1 for r in results
        if not r.success and r.error_type != ErrorType.TEST_SKIP
    )

    print()
    print("=" * 60)
    print(f"  结果: {passed}/{len(results)} 通过, {failed} 失败, {skipped} 跳过")
    print("=" * 60)

    if failed > 0:
        print()
        print("失败测试:")
        for r in results:
            if not r.success and r.error_type != ErrorType.TEST_SKIP:
                print(f"  - {r.test_name}: {r.message}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
