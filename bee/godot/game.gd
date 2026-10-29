extends Control
## 主场景：连接 sim_core 桥接服务，驱动模拟并在 UI 上呈现（零输入 idle RPG）。
##
## ⚠️ 脚手架未在本机验证（无 Godot 安装），需用户在 Godot 4.x 中实测。

@onready var _log_view: RichTextLabel = $LogView
@onready var _stats: Label = $Stats
@onready var _timer: Timer = $StepTimer

var _bridge: Node = preload("res://sim_bridge.gd").new()
const SEED := 12345
const DT := 0.05


func _ready() -> void:
	_bridge.connected.connect(_on_connected)
	_bridge.state_received.connect(_on_state)
	_bridge.disconnected.connect(_on_disconnected)
	add_child(_bridge)
	_bridge.connect_to_sim()


func _on_connected() -> void:
	# save_path 留空 -> 确定性新建（与黄金基准一致）
	_bridge.init_sim(SEED)


func _on_state(log_messages: Array, fingerprint: Dictionary) -> void:
	_log_view.text = "\n".join(log_messages)
	_stats.text = "Lv %d | 金币 %d | 区域 %s | 时间 %.1f | 击杀 %d | 死亡 %d" % [
		fingerprint["level"], fingerprint["gold"], str(fingerprint["region_id"]),
		fingerprint["game_time"], fingerprint["kills"], fingerprint["deaths"]
	]


func _on_disconnected() -> void:
	_stats.text = "已断开（桥接服务退出）"


func _on_step_timeout() -> void:
	_bridge.step(DT)
	_bridge.request_state()


func _exit_tree() -> void:
	_bridge.quit_sim()
