extends Node
## SimBridge — Godot 端 TCP JSON-line 客户端
##
## 连接 sim_core 桥接服务（在 bee 根目录运行：
##     python -m src.sim_core.bridge --port 18765
## ），按行收发 JSON 指令，驱动模拟并把状态回传 UI。
##
## 协议（每行一条 JSON）：
##   发 -> {"cmd":"init","seed":int,"save_path":str}
##        {"cmd":"step","dt":float}
##        {"cmd":"state"}
##        {"cmd":"new_game","name":str,"race":str,"char_class":str,"seed":int?}
##        {"cmd":"quit"}
##   收 <- {"ok":true,...}  |  {"ok":false,"error":str}
##         state 响应含 {"log_messages":[...], "fingerprint":{...}}
##
## ⚠️ 脚手架未在本机验证（无 Godot 安装），需用户在 Godot 4.x 中实测。

const HOST := "127.0.0.1"
const PORT := 18765

var _tcp := StreamPeerTCP.new()
var _buffer := ""
var _was_connected := false

signal connected()
signal disconnected()
signal state_received(log_messages: Array, fingerprint: Dictionary)


func connect_to_sim() -> void:
	var err := _tcp.connect_to_host(HOST, PORT)
	if err != OK:
		push_error("sim_bridge: 无法连接 %s:%d (err %d)" % [HOST, PORT, err])


func _process(_delta: float) -> void:
	_tcp.poll()  # Godot 4.x：必须每帧 poll，否则连接状态不更新、握手不推进
	var status := _tcp.get_status()
	if status == StreamPeerTCP.STATUS_CONNECTED:
		if not _was_connected:
			_was_connected = true
			connected.emit()
		var avail := _tcp.get_available_bytes()
		if avail > 0:
			_buffer += _tcp.get_string(avail)
			var idx := _buffer.find("\n")
			while idx >= 0:
				var line := _buffer.substr(0, idx).strip_edges()
				_buffer = _buffer.substr(idx + 1)
				if line.length() > 0:
					_handle_line(line)
				idx = _buffer.find("\n")
	elif status == StreamPeerTCP.STATUS_NONE:
		if _was_connected:
			_was_connected = false
			disconnected.emit()
	# STATUS_CONNECTING / STATUS_ERROR 暂不处理


func _handle_line(line: String) -> void:
	var res: Variant = JSON.parse_string(line)
	if typeof(res) != TYPE_DICTIONARY:
		return
	if res.get("ok", false) and res.has("log_messages") and res.has("fingerprint"):
		state_received.emit(res["log_messages"], res["fingerprint"])
	elif not res.get("ok", true):
		push_error("sim_bridge 错误: " + str(res.get("error", "未知")))


func _send(cmd: String, extra := {}) -> void:
	if _tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return
	var msg := {"cmd": cmd}
	for k in extra:
		msg[k] = extra[k]
	# 用 put_data 发原始 UTF-8 字节；put_string 会额外写 4 字节长度前缀，
	# 与 bridge.py 的「按 \n 分隔的纯文本行」协议不兼容（会被当成 bad json）。
	_tcp.put_data((JSON.stringify(msg) + "\n").to_utf8_buffer())


func init_sim(seed: int, save_path: String = "") -> void:
	_send("init", {"seed": seed, "save_path": save_path})


func step(dt: float) -> void:
	_send("step", {"dt": dt})


func request_state() -> void:
	_send("state")


func new_game(name: String, race: String, char_class: String, seed: int = -1) -> void:
	var extra := {"name": name, "race": race, "char_class": char_class}
	if seed >= 0:
		extra["seed"] = seed
	_send("new_game", extra)


func quit_sim() -> void:
	_send("quit")
