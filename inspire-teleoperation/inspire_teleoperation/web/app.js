const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const copy = {
  zh: {
    workspace: "工作区", connection: "设备接入", dashboard: "实时控制", tactile: "触觉反馈", systemLog: "系统日志", systemState: "系统状态", localConsole: "本地控制台", preferences: "界面设置", appearance: "外观",
    setupEyebrow: "设备接入", setupTitle: "建立遥操作连接", setupLead: "配置设备与控制策略，确认安全后启动会话。", stepConfigure: "配置", stepConnect: "连接", stepControl: "控制",
    devices: "设备", devicesHelp: "选择要控制的灵巧手并确认网络地址", oneRequired: "至少启用一台", leftHand: "左手", rightHand: "右手", host: "主机地址", deviceId: "设备 ID",
    controlParams: "控制策略", controlHelp: "设置通信频率与关节运动速度", port: "Modbus 端口", timeout: "请求超时", speedMode: "速度模式", adaptive: "自适应 2.0", adaptive_v2: "自适应 2.0", adaptive_v1: "自适应 1.0", fixed: "固定速度", fixedSpeed: "固定速度", fixedSpeedHint: "仅固定模式生效", questRate: "Quest 采样率", handRate: "手部指令率", tactileRateSetting: "触觉轮询率", tactileRateHint: "范围 1–60 Hz，仅在触觉页采集",
    advancedOptions: "会话选项", advancedHint: "跟踪启动、标记显示与断开行为", startNow: "连接后立即跟踪", startNowHelp: "工作区清空时使用", hideMarkers: "隐藏 Quest 标记", hideMarkersHelp: "不影响数据采集", openExit: "断开设备时张手", openExitHelp: "安装工具时保持关闭",
    safetyCheck: "连接前检查", safetyIntro: "设备可能在连接后立即运动", checkWorkspace: "设备固定与线缆状态已检查", checkNetwork: "设备地址与网络已确认", checkSpeed: "已选择合适的速度策略", safetyConfirm: "我确认工作区内没有人员、工具或易损物体", safetyDetail: "此确认是建立设备连接的必要条件。", connect: "连接设备", localOnly: "仅在本机建立连接",
    liveEyebrow: "实时遥操作", dashboardTitle: "运行控制台", dashboardLead: "监控连接、数据链路与关节状态。", session: "会话", teleopStatus: "遥操作状态", questData: "Quest 数据", loopRate: "主循环频率", safetyTitle: "进入工作区前", safetyPause: "请先停止跟踪", run: "开始跟踪", stopTracking: "停止跟踪", switchSpeed: "切换速度", motionFilterOff: "微滤波：关", motionFilterOn: "微滤波：开", calibrateForce: "力传感器校准", disconnect: "断开设备",
    tactileEyebrow: "触觉反馈", tactileTitle: "触觉热力图", tactileLead: "查看每个触觉区域的压力分布，悬停方格可读取精确数值。", bothHands: "双手", tactileStatus: "数据状态", sampleRate: "采样频率", waitingTactile: "等待首帧", tactileReady: "数据已更新", tactileNoData: "正在读取触觉数据…", tactileError: "读取失败", row: "行", column: "列", sensorValue: "数值", rawValue: "原始值", processedValue: "净化值",
    filterTitle: "噪声处理", filterLead: "在基础逐点滤波与力辅助增强方案之间按场景切换", filterUncalibrated: "待零点学习", filterCalibrating: "正在学习", filterCalibrated: "已启用", filterIncomplete: "部分手部待学习", filterFailed: "学习失败", filterStepPrepare: "保持灵巧手悬空、静止", filterStepLearn: "学习 3 秒静态零点", filterStepUse: "查看净化后的触觉", filterDisplay: "热力图数据", filterProcessed: "净化后", filterRaw: "原始值", filterAlgorithm: "处理方案", filterBasic: "基础滤波", filterEnhanced: "力辅助增强", filterSensitivity: "灵敏度", filterSensitive: "灵敏", filterBalanced: "均衡（推荐）", filterStable: "稳定", filterBasicDrift: "缓慢漂移补偿", filterBasicDriftHelp: "仅在未检测到接触时微调逐点零点", filterDrift: "力辅助基线恢复", filterDriftHelp: "无接触时慢跟踪；确认卸载后恢复压后偏移", filterCalibrate: "学习静态零点", filterRecalibrate: "重新学习零点", filterCancel: "取消学习", filterReadyHint: "预热并保持无接触后开始；每次重连或底层力校准后请重新学习", filterKeepStill: "请勿触碰 · 正在学习触觉与六路力零点", filterComplete: "静态零点学习完成，两套处理方案均可使用", filterCompleteNoForce: "触觉零点学习完成；基础滤波可用，增强方案采用保守恢复模式", filterNotEnoughSamples: "有效样本不足，请确认触觉数据正常后重试", filterSelectHand: "请先选择并等待手部触觉数据", filterBaselinePoints: "已学习触点", filterActivePoints: "当前接触", filterSuppressedPoints: "本帧抑制", filterModuleStates: "模块状态", filterNoContactShort: "空闲", filterContactShort: "接触", filterRecoveryShort: "恢复", filterRawCaptureNote: "处理只影响热力图；下方采集文件保存原始触觉及同步六路力数据，便于复查和离线标定。", filterResetAfterForce: "底层力校准已完成，请重新学习触觉与六路力静态零点。",
    captureTitle: "触觉信息采集", captureLead: "按指定频率将当前所选手部的触觉帧流式写入文件", captureFrequency: "采集频率", captureFrequencyHint: "不得高于当前触觉数据率", captureDuration: "采集时间", captureDurationHint: "最长 24 小时", captureOutput: "输出路径", captureOutputHint: "可填写目录或以 .jsonl 结尾的文件路径", captureFormat: "输出格式", captureFormatHint: "每行一帧，支持流式读取", captureStart: "开始采集", captureStop: "停止采集", captureIdle: "未开始", captureRecording: "采集中", captureStopping: "正在停止", captureCompleted: "采集完成", captureStopped: "已停止", captureFailed: "采集失败", captureWaiting: "等待开始采集", captureSamples: "帧", captureSavedTo: "输出文件", captureSelectHand: "请先选择要采集的手部。", captureProgress: "采集进度", captureDropped: "丢弃帧",
    joint: "关节", position: "实际 / 目标", speed: "速度", sixJoints: "6 个关节", latestEvents: "最近 4 条运行事件", viewAllLogs: "查看全部", logsEyebrow: "运行记录", logsLead: "查看当前控制会话的完整运行事件。", logEntries: "条记录", clearLogs: "清空日志", currentSession: "当前会话", realtimeUpdates: "日志实时更新", liveUpdate: "实时", time: "时间", clear: "清空", level: "级别", event: "事件", noEvents: "暂无运行日志",
    cancel: "取消", confirm: "确认", waitingSetup: "等待配置", connecting: "正在连接", disconnecting: "正在断开", live: "已连接", stopping: "正在停止", stopped: "已停止", error: "连接错误", paused: "跟踪已停止", running: "正在跟踪", waitingData: "等待手部数据", ready: "数据就绪", unavailable: "无数据", connected: "已连接", enabled: "已启用", disabled: "未启用",
    fontSize: "界面字号", fontSizeHelp: "输入精确字号，整个控制台会按比例调整。", themeColor: "主题色", themeColorHelp: "选择预设颜色，或使用自定义颜色。", customColor: "自定义", resetAppearance: "恢复默认", shutdownService: "关闭控制服务", disconnectBeforeShutdown: "请先断开设备，再关闭控制服务。",
    setupFailed: "无法提交配置", enableOneHandError: "请至少启用一只手。", duplicateHostError: "左右手不能使用相同的主机地址。", safetyConfirmationError: "请勾选工作区安全确认。", invalidSettingsError: "请检查高亮的设备地址或控制参数。", actionFailed: "操作失败", runTitle: "开始手部跟踪？", runCopy: "确认双手工作区已经清空。开始后，Quest 手势将实时驱动灵巧手。", calibrateForceTitle: "校准力传感器？", calibrateForceCopy: "移除灵巧手上的外力与接触物。确认后将停止跟踪，并校准所有已连接的手。", calibrationRequested: "正在校准力传感器，请保持灵巧手不受外力。", calibrationRunningTitle: "正在校准", calibrationRunningCopy: "正在等待最短校准时间并验证六路力值稳定，请勿接触灵巧手。", calibrationCompletedTitle: "校准完成", calibrationCompletedCopy: "所有已连接灵巧手的零点力值已经稳定。确认后关闭此窗口。", calibrationFailedTitle: "校准失败", calibrationFailedCopy: "力值未能稳定或设备通信失败。", acknowledge: "确定", disconnectTitle: "断开当前设备？", disconnectCopy: "跟踪将停止，Modbus 与 Quest 会话将关闭。随后可以立即修改设备接入设置并重新连接。", quitTitle: "关闭控制服务？", quitCopy: "所有设备会断开，当前页面也将停止提供服务。下次使用需要重新启动程序。", jointNames: ["小指", "无名指", "中指", "食指", "拇指", "旋转"], tactileRegions: { little_tip: "小指尖", little_nail: "小指背", little_pad: "小指腹", ring_tip: "无名指尖", ring_nail: "无名指背", ring_pad: "无名指腹", middle_tip: "中指尖", middle_nail: "中指背", middle_pad: "中指腹", index_tip: "食指尖", index_nail: "食指背", index_pad: "食指腹", thumb_tip: "拇指尖", thumb_nail: "拇指背", thumb_middle: "拇指中部", thumb_pad: "拇指腹", palm: "掌心" }, tactileGroups: { little: "小指", ring: "无名指", middle: "中指", index: "食指", thumb: "拇指", palm: "掌心" }
  },
  en: {
    workspace: "Workspace", connection: "Device setup", dashboard: "Live control", tactile: "Tactile feedback", systemLog: "System log", systemState: "System state", localConsole: "Local console", preferences: "Interface settings", appearance: "Appearance",
    setupEyebrow: "Device setup", setupTitle: "Start a teleoperation session", setupLead: "Configure devices and control behavior, then complete the safety check.", stepConfigure: "Configure", stepConnect: "Connect", stepControl: "Control",
    devices: "Devices", devicesHelp: "Choose each dexterous hand and verify its network address", oneRequired: "One required", leftHand: "Left hand", rightHand: "Right hand", host: "Host address", deviceId: "Device ID",
    controlParams: "Control strategy", controlHelp: "Set communication rates and joint motion speed", port: "Modbus port", timeout: "Request timeout", speedMode: "Speed mode", adaptive: "Adaptive 2.0", adaptive_v2: "Adaptive 2.0", adaptive_v1: "Adaptive 1.0", fixed: "Fixed speed", fixedSpeed: "Fixed speed", fixedSpeedHint: "Used in fixed mode only", questRate: "Quest polling", handRate: "Hand command rate", tactileRateSetting: "Tactile polling", tactileRateHint: "1–60 Hz; sampled only on the tactile page",
    advancedOptions: "Session options", advancedHint: "Tracking start, marker display, and disconnect behavior", startNow: "Track immediately", startNowHelp: "Use only in a clear workspace", hideMarkers: "Hide Quest markers", hideMarkersHelp: "Capture is unaffected", openExit: "Open hands on disconnect", openExitHelp: "Keep off when tools are attached",
    safetyCheck: "Preflight check", safetyIntro: "Devices may move immediately after connection", checkWorkspace: "Device mounting and cables checked", checkNetwork: "Device addresses and network verified", checkSpeed: "Appropriate speed strategy selected", safetyConfirm: "I confirm the workspaces are clear of people, tools, and fragile objects", safetyDetail: "This confirmation is required to establish a connection.", connect: "Connect devices", localOnly: "Connection stays on this machine",
    liveEyebrow: "Live teleoperation", dashboardTitle: "Operations console", dashboardLead: "Monitor connections, data flow, and joint state.", session: "Session", teleopStatus: "Teleop status", questData: "Quest data", loopRate: "Main loop rate", safetyTitle: "Before entering workspace", safetyPause: "Stop tracking first", run: "Start tracking", stopTracking: "Stop tracking", switchSpeed: "Switch speed", motionFilterOff: "Micro-filter: Off", motionFilterOn: "Micro-filter: On", calibrateForce: "Calibrate force sensors", disconnect: "Disconnect devices",
    tactileEyebrow: "Tactile feedback", tactileTitle: "Tactile heatmap", tactileLead: "Inspect pressure across every tactile region; hover a cell for its exact value.", bothHands: "Both hands", tactileStatus: "Live data", sampleRate: "Sample rate", waitingTactile: "Waiting for first frame", tactileReady: "Data updated", tactileNoData: "Reading tactile data…", tactileError: "Read failed", row: "Row", column: "Column", sensorValue: "Value", rawValue: "Raw", processedValue: "Filtered",
    filterTitle: "Noise processing", filterLead: "Switch between basic per-cell filtering and force-assisted processing for each scenario", filterUncalibrated: "Baseline required", filterCalibrating: "Learning", filterCalibrated: "Enabled", filterIncomplete: "Some hands need learning", filterFailed: "Learning failed", filterStepPrepare: "Keep the hands free and still", filterStepLearn: "Learn a 3-second baseline", filterStepUse: "View filtered tactile data", filterDisplay: "Heatmap data", filterProcessed: "Filtered", filterRaw: "Raw", filterAlgorithm: "Processing mode", filterBasic: "Basic filter", filterEnhanced: "Force-assisted", filterSensitivity: "Sensitivity", filterSensitive: "Sensitive", filterBalanced: "Balanced (recommended)", filterStable: "Stable", filterBasicDrift: "Slow drift compensation", filterBasicDriftHelp: "Adjust each baseline only while no contact is detected", filterDrift: "Force-assisted recovery", filterDriftHelp: "Track slowly when idle; recover post-load offset after confirmed unloading", filterCalibrate: "Learn idle baseline", filterRecalibrate: "Relearn baseline", filterCancel: "Cancel learning", filterReadyHint: "Warm up and remove all contact first; relearn after each reconnect or low-level force calibration", filterKeepStill: "Do not touch · learning tactile and six-force baselines", filterComplete: "Idle baselines learned; both processing modes are available", filterCompleteNoForce: "Tactile baselines learned; basic filtering is available and force-assisted mode uses conservative recovery", filterNotEnoughSamples: "Not enough valid samples. Check tactile data and try again", filterSelectHand: "Select a hand and wait for tactile data first", filterBaselinePoints: "Learned cells", filterActivePoints: "Active contact", filterSuppressedPoints: "Suppressed now", filterModuleStates: "Module states", filterNoContactShort: "Idle", filterContactShort: "Contact", filterRecoveryShort: "Recovery", filterRawCaptureNote: "Processing affects only the heatmap. Captures keep raw tactile values and synchronized six-force data for review and offline calibration.", filterResetAfterForce: "Low-level force calibration completed. Relearn tactile and six-force idle baselines.",
    captureTitle: "Tactile data capture", captureLead: "Stream tactile frames from the selected hands to a file at a defined rate", captureFrequency: "Capture rate", captureFrequencyHint: "Cannot exceed the available tactile data rate", captureDuration: "Duration", captureDurationHint: "Up to 24 hours", captureOutput: "Output path", captureOutputHint: "Enter a directory or a file ending in .jsonl", captureFormat: "Output format", captureFormatHint: "One frame per line for streaming reads", captureStart: "Start capture", captureStop: "Stop capture", captureIdle: "Not started", captureRecording: "Recording", captureStopping: "Stopping", captureCompleted: "Complete", captureStopped: "Stopped", captureFailed: "Capture failed", captureWaiting: "Waiting to start", captureSamples: "frames", captureSavedTo: "Output file", captureSelectHand: "Select at least one hand to capture.", captureProgress: "Capture progress", captureDropped: "Dropped frames",
    joint: "Joint", position: "Actual / target", speed: "Speed", sixJoints: "6 joints", latestEvents: "Latest 4 runtime events", viewAllLogs: "View all", logsEyebrow: "Runtime records", logsLead: "Review the complete event history for the current control session.", logEntries: "entries", clearLogs: "Clear logs", currentSession: "Current session", realtimeUpdates: "Logs update in real time", liveUpdate: "Live", time: "Time", clear: "Clear", level: "Level", event: "Event", noEvents: "No runtime events",
    cancel: "Cancel", confirm: "Confirm", waitingSetup: "Awaiting setup", connecting: "Connecting", disconnecting: "Disconnecting", live: "Connected", stopping: "Stopping", stopped: "Stopped", error: "Connection error", paused: "Tracking stopped", running: "Tracking", waitingData: "Waiting for hand data", ready: "Data ready", unavailable: "Unavailable", connected: "Connected", enabled: "Enabled", disabled: "Disabled",
    fontSize: "Interface font size", fontSizeHelp: "Enter an exact size to scale console typography.", themeColor: "Theme color", themeColorHelp: "Choose a preset or use a custom color.", customColor: "Custom", resetAppearance: "Reset appearance", shutdownService: "Stop control service", disconnectBeforeShutdown: "Disconnect the devices before stopping the control service.",
    setupFailed: "Could not submit configuration", enableOneHandError: "Enable at least one hand.", duplicateHostError: "Left and right hands cannot use the same host address.", safetyConfirmationError: "Confirm that the hand workspace is clear.", invalidSettingsError: "Check the highlighted device addresses or control settings.", actionFailed: "Action failed", runTitle: "Start hand tracking?", runCopy: "Confirm both hand workspaces are clear. Quest gestures will drive the dexterous hands in real time.", calibrateForceTitle: "Calibrate force sensors?", calibrateForceCopy: "Remove all loads and contact from the hands. Tracking will stop and every connected hand will be calibrated.", calibrationRequested: "Calibrating force sensors. Keep the hands unloaded.", calibrationRunningTitle: "Calibrating", calibrationRunningCopy: "Waiting for the minimum calibration time and stable readings from all six force channels. Do not touch the hands.", calibrationCompletedTitle: "Calibration complete", calibrationCompletedCopy: "Zero-force readings are stable on every connected hand. Confirm to close this window.", calibrationFailedTitle: "Calibration failed", calibrationFailedCopy: "Force readings did not stabilize or device communication failed.", acknowledge: "OK", disconnectTitle: "Disconnect current devices?", disconnectCopy: "Tracking, Modbus, and the Quest session will stop. You can then edit device settings and reconnect immediately.", quitTitle: "Stop the control service?", quitCopy: "All devices will disconnect and this page will stop responding. Restart the program to use it again.", jointNames: ["Little", "Ring", "Middle", "Index", "Thumb", "Rotate"], tactileRegions: { little_tip: "Little tip", little_nail: "Little nail", little_pad: "Little pad", ring_tip: "Ring tip", ring_nail: "Ring nail", ring_pad: "Ring pad", middle_tip: "Middle tip", middle_nail: "Middle nail", middle_pad: "Middle pad", index_tip: "Index tip", index_nail: "Index nail", index_pad: "Index pad", thumb_tip: "Thumb tip", thumb_nail: "Thumb nail", thumb_middle: "Thumb middle", thumb_pad: "Thumb pad", palm: "Palm" }, tactileGroups: { little: "Little", ring: "Ring", middle: "Middle", index: "Index", thumb: "Thumb", palm: "Palm" }
  }
};

let language = "zh";
let configured = false;
let lastPhase = "setup";
let lastDetail = "";
let hiddenLogCount = 0;
let logFingerprint = "";
let latestMessages = [];
let latestSnapshot = null;
let latestConfig = {};
let activeNav = "setup";
let setupSubmitting = false;
let setupErrors = [];
let tactileSelection = [];
let tactileFingerprint = "";
let activeTactileCell = null;
let tactileDisplayMode = "filtered";
let tactileProcessingMode = "enhanced";
let lastForceCalibrationState = "idle";
let latestCapture = { state: "idle" };
let captureRequestError = "";
let calibrationDialogStage = "idle";
let calibrationDialogDetail = "";
const preferenceKey = "inspire-console-appearance-v1";
const setupPreferenceKey = "inspire-console-setup-v1";
const capturePreferenceKey = "inspire-console-capture-v1";
const languagePreferenceKey = "inspire-console-language-v1";
const setupPreferenceFields = [
  "left_enabled", "left_host", "left_device_id",
  "right_enabled", "right_host", "right_device_id",
  "modbus_port", "modbus_timeout", "target_speed", "speed_mode",
  "frequency", "hand_frequency", "tactile_frequency",
  "start", "open_on_exit", "hide_hand_markers"
];
const defaultPreferences = { fontSize: 12, accent: "#a7f432" };
const defaultCapturePreferences = { frequency: 10, duration: 10, output: "tactile_captures" };
const tactileCalibrationDurationMs = 3000;
const tactileCalibrationMinimumSamples = 15;
const tactileSensitivityProfiles = {
  sensitive: { thresholdScale: 0.75, smoothing: 0.65 },
  balanced: { thresholdScale: 1, smoothing: 0.45 },
  stable: { thresholdScale: 1.5, smoothing: 0.3 }
};
const tactileForceIndex = { little: 0, ring: 1, middle: 2, index: 3, thumb: 4 };
const tactileBaselineTauSeconds = 30;
const tactileRecoveryTauSeconds = 4;
const tactileRecoveryConfirmSeconds = 0.5;
let tactileFilter = createTactileFilterState();
let preferences = { ...defaultPreferences };

const tactileGroupSpecs = [
  ["little", ["little_tip", "little_nail", "little_pad"]],
  ["ring", ["ring_tip", "ring_nail", "ring_pad"]],
  ["middle", ["middle_tip", "middle_nail", "middle_pad"]],
  ["index", ["index_tip", "index_nail", "index_pad"]],
  ["thumb", ["thumb_tip", "thumb_nail", "thumb_middle", "thumb_pad"]],
  ["palm", ["palm"]]
];

function t(key) { return copy[language][key] ?? key; }

function createTactileFilterState() {
  return {
    status: "idle",
    sides: [],
    startedAt: 0,
    timer: null,
    samples: {},
    sampleRevisions: {},
    baselines: {},
    modeBaselines: { basic: {}, enhanced: {} },
    deadbands: {},
    forceBaselines: {},
    forceDeadbands: {},
    calibratedSides: new Set(),
    temporal: {},
    moduleStates: {},
    displayCache: {},
    displayRevisions: {},
    pointCount: 0,
    activeCount: null,
    suppressedCount: null,
    moduleStateCounts: null,
    messageKey: "filterReadyHint"
  };
}

function updateShutdownAvailability(hasSession = lastPhase !== "setup") {
  const button = $('#shutdown-button');
  button.setAttribute("aria-disabled", hasSession ? "true" : "false");
  button.dataset.blockedHint = t("disconnectBeforeShutdown");
  button.setAttribute("aria-label", hasSession
    ? `${t("shutdownService")}。${t("disconnectBeforeShutdown")}`
    : t("shutdownService"));
}

function normalizePreferences(value = {}) {
  const fontSize = Math.max(10, Math.min(18, Number(value.fontSize) || defaultPreferences.fontSize));
  const accent = /^#[0-9a-f]{6}$/i.test(value.accent || "") ? value.accent.toLowerCase() : defaultPreferences.accent;
  return { fontSize, accent };
}

function loadPreferences() {
  try { preferences = normalizePreferences(JSON.parse(localStorage.getItem(preferenceKey) || "{}")); }
  catch (_error) { preferences = { ...defaultPreferences }; }
  applyPreferences(false);
}

function applyPreferences(persist = true) {
  preferences = normalizePreferences(preferences);
  document.documentElement.style.setProperty("--ui-font-size", `${preferences.fontSize}px`);
  document.documentElement.style.setProperty("--accent", preferences.accent);
  $('#font-size-input').value = preferences.fontSize;
  $('#custom-color-input').value = preferences.accent;
  $$('.theme-swatch').forEach(button => button.classList.toggle("active", button.dataset.color.toLowerCase() === preferences.accent));
  if (persist) {
    try { localStorage.setItem(preferenceKey, JSON.stringify(preferences)); }
    catch (_error) { /* Appearance still applies when storage is unavailable. */ }
  }
}

function setFontSize(value) {
  if (!Number.isFinite(Number(value))) return;
  preferences.fontSize = Math.round(Number(value));
  applyPreferences();
}

function loadSetupPreferences() {
  try {
    const saved = JSON.parse(localStorage.getItem(setupPreferenceKey) || "{}");
    if (!saved || typeof saved !== "object" || Array.isArray(saved)) return {};
    return Object.fromEntries(setupPreferenceFields
      .filter(name => {
        if (!Object.hasOwn(saved, name)) return false;
        const field = $('#setup-form').elements[name];
        return field.type === "checkbox"
          ? typeof saved[name] === "boolean"
          : ["string", "number"].includes(typeof saved[name]);
      })
      .map(name => [name, saved[name]]));
  } catch (_error) {
    return {};
  }
}

function loadLanguagePreference() {
  try {
    const saved = localStorage.getItem(languagePreferenceKey);
    return saved === "zh" || saved === "en" ? saved : "";
  } catch (_error) {
    return "";
  }
}

function saveSetupPreferences() {
  const form = $('#setup-form');
  const saved = Object.fromEntries(setupPreferenceFields.map(name => {
    const field = form.elements[name];
    return [name, field.type === "checkbox" ? field.checked : field.value];
  }));
  try { localStorage.setItem(setupPreferenceKey, JSON.stringify(saved)); }
  catch (_error) { /* Form settings still work when storage is unavailable. */ }
}

function loadCapturePreferences() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(capturePreferenceKey) || "{}"); }
  catch (_error) { /* Fall back to capture defaults. */ }
  const form = $('#tactile-capture-form');
  form.elements.capture_frequency.value = Number(saved.frequency) > 0 ? saved.frequency : defaultCapturePreferences.frequency;
  form.elements.capture_duration.value = Number(saved.duration) > 0 ? saved.duration : defaultCapturePreferences.duration;
  form.elements.capture_output.value = typeof saved.output === "string" && saved.output.trim() ? saved.output : defaultCapturePreferences.output;
}

function saveCapturePreferences() {
  const form = $('#tactile-capture-form');
  const value = {
    frequency: Number(form.elements.capture_frequency.value),
    duration: Number(form.elements.capture_duration.value),
    output: form.elements.capture_output.value
  };
  try { localStorage.setItem(capturePreferenceKey, JSON.stringify(value)); }
  catch (_error) { /* Capture settings still apply when storage is unavailable. */ }
}

function applyLanguage() {
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  $$('[data-i18n]').forEach(element => { element.textContent = t(element.dataset.i18n); });
  $('#language-button').textContent = language === "zh" ? "EN" : "中";
  $('#page-name').textContent = lastPhase === "setup" ? t("connection") : t(activeNav === "tactile" ? "tactile" : activeNav === "logs" ? "systemLog" : "dashboard");
  updateShutdownAvailability();
  updateHandFields();
  if (latestSnapshot) {
    renderSnapshot(latestSnapshot);
    tactileFingerprint = "";
    activeTactileCell = null;
    $('#tactile-tooltip').hidden = true;
    $('#tactile-hands').innerHTML = "";
    renderTactile(latestSnapshot.tactile || {});
  }
  renderTactileFilterPanel();
  if (setupErrors.length) renderSetupErrors(setupErrors);
  renderTactileCapture(latestCapture);
  logFingerprint = "";
  renderLogs(latestMessages);
}

function setForm(config) {
  Object.entries(config).forEach(([name, value]) => {
    const field = $(`[name="${name}"]`);
    if (!field) return;
    if (field.type === "checkbox") field.checked = value;
    else field.value = value;
  });
  updateHandFields();
  updateSpeedFields();
}

function updateHandFields() {
  ["left", "right"].forEach(side => {
    const enabled = $(`[name="${side}_enabled"]`).checked;
    const box = $(`#${side}-config`);
    box.classList.toggle("disabled", !enabled);
    $$(`input:not([name="${side}_enabled"])`, box).forEach(input => { input.disabled = !enabled; });
    $(`[data-side-summary="${side}"]`).textContent = t(enabled ? "enabled" : "disabled");
  });
}

function updateSpeedFields() {
  const fixed = $('[name="speed_mode"]').value === "fixed";
  $('#fixed-speed-field').classList.toggle("inactive", !fixed);
}

function formPayload() {
  const form = $('#setup-form');
  const value = name => form.elements[name].value;
  const checked = name => form.elements[name].checked;
  return {
    left_enabled: checked("left_enabled"), left_host: value("left_host"), left_device_id: Number(value("left_device_id")),
    right_enabled: checked("right_enabled"), right_host: value("right_host"), right_device_id: Number(value("right_device_id")),
    modbus_port: Number(value("modbus_port")), modbus_timeout: Number(value("modbus_timeout")), target_speed: Number(value("target_speed")),
    speed_mode: value("speed_mode"), frequency: Number(value("frequency")), hand_frequency: Number(value("hand_frequency")), tactile_frequency: Number(value("tactile_frequency")),
    start: checked("start"), open_on_exit: checked("open_on_exit"), hide_hand_markers: checked("hide_hand_markers"), safety_confirmed: checked("safety_confirmed")
  };
}

function renderSetupErrors(errors) {
  setupErrors = [...new Set(errors.filter(Boolean))];
  const container = $('#setup-error');
  if (!setupErrors.length) {
    container.innerHTML = "";
    return;
  }
  container.innerHTML = `<strong>${escapeHtml(t("setupFailed"))}</strong><ul>${setupErrors.map(error => `<li>${escapeHtml(t(error))}</li>`).join("")}</ul>`;
}

function clearSetupErrors() {
  setupErrors = [];
  $('#setup-error').innerHTML = "";
  $$('.field-invalid', $('#setup-form')).forEach(element => element.classList.remove("field-invalid"));
  $$('[aria-invalid="true"]', $('#setup-form')).forEach(element => element.removeAttribute("aria-invalid"));
}

function validateSetupForm(form) {
  clearSetupErrors();
  const errors = [];
  const leftEnabled = form.elements.left_enabled.checked;
  const rightEnabled = form.elements.right_enabled.checked;
  if (!leftEnabled && !rightEnabled) {
    errors.push("enableOneHandError");
    $('#left-config').classList.add("field-invalid");
    $('#right-config').classList.add("field-invalid");
  }
  const leftHost = form.elements.left_host.value.trim().toLocaleLowerCase();
  const rightHost = form.elements.right_host.value.trim().toLocaleLowerCase();
  if (leftEnabled && rightEnabled && leftHost && leftHost === rightHost) {
    errors.push("duplicateHostError");
    [form.elements.left_host, form.elements.right_host].forEach(field => {
      field.classList.add("field-invalid");
      field.setAttribute("aria-invalid", "true");
    });
    $('#left-config').classList.add("field-invalid");
    $('#right-config').classList.add("field-invalid");
  }
  if (!form.elements.safety_confirmed.checked) {
    errors.push("safetyConfirmationError");
    $('.safety-check').classList.add("field-invalid");
    form.elements.safety_confirmed.setAttribute("aria-invalid", "true");
  }

  let invalidSettings = false;
  $$('input, select', form).forEach(field => {
    if (field.disabled || field.type === "checkbox" || field.type === "submit") return;
    const emptyHost = field.name.endsWith("_host") && !field.value.trim();
    if (!field.validity.valid || emptyHost) {
      invalidSettings = true;
      field.classList.add("field-invalid");
      field.setAttribute("aria-invalid", "true");
    }
  });
  if (invalidSettings) errors.push("invalidSettingsError");
  renderSetupErrors(errors);
  return errors.length === 0;
}

async function post(path, payload) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
  return body;
}

function phaseLabel(phase) {
  return t({ setup: "waitingSetup", connecting: "connecting", disconnecting: "disconnecting", live: "live", stopping: "stopping", stopped: "stopped", error: "error" }[phase] || phase);
}

function renderPhase(state) {
  const phaseChanged = lastPhase !== state.phase;
  if (phaseChanged && (state.phase === "live" || state.phase === "setup")) resetTactileFilter();
  lastPhase = state.phase;
  $('#connection-label').textContent = phaseLabel(state.phase);
  $('#connection-dot').className = `status-dot ${state.phase === "live" ? "live" : state.phase === "error" ? "error" : ""}`;
  const hasSession = state.phase !== "setup";
  updateShutdownAvailability(hasSession);
  if (!hasSession) activeNav = "setup";
  else if (phaseChanged || activeNav === "setup") activeNav = "dashboard";
  if (state.phase !== "live" && activeNav === "tactile") activeNav = "dashboard";
  const showTactile = state.phase === "live" && activeNav === "tactile";
  const showLogs = hasSession && activeNav === "logs";
  $('#setup-view').hidden = hasSession;
  $('#dashboard-view').hidden = !hasSession || showTactile || showLogs;
  $('#tactile-view').hidden = !showTactile;
  $('#logs-view').hidden = !showLogs;
  $('#top-session').hidden = !hasSession;
  $('#page-name').textContent = !hasSession ? t("connection") : t(showTactile ? "tactile" : showLogs ? "systemLog" : "dashboard");
  const setupNav = $('[data-nav="setup"]');
  const dashboardNav = $('[data-nav="dashboard"]');
  const tactileNav = $('[data-nav="tactile"]');
  const logsNav = $('[data-nav="logs"]');
  setupNav.disabled = hasSession;
  dashboardNav.disabled = !hasSession;
  tactileNav.disabled = state.phase !== "live";
  logsNav.disabled = !hasSession;
  $$('.nav-item').forEach(item => item.classList.toggle("active", item.dataset.nav === activeNav));
  if (state.phase === "error" && state.detail && (phaseChanged || state.detail !== lastDetail)) addLocalLog("error", state.detail);
  const connectButton = $('.primary-button', $('#setup-form'));
  if (state.phase === "setup" && !setupSubmitting && (
    phaseChanged || state.detail !== lastDetail || connectButton.disabled
  )) {
    setForm(state.config);
    $('[name="safety_confirmed"]').checked = false;
    connectButton.disabled = false;
    if (state.detail) renderSetupErrors([state.detail]);
    else clearSetupErrors();
  }
  lastDetail = state.detail || "";
  $$('.control-actions button').forEach(button => { button.disabled = state.phase !== "live"; });
}

function formatDuration(seconds = 0) {
  const total = Math.max(0, Math.floor(seconds));
  return [Math.floor(total / 3600), Math.floor(total % 3600 / 60), total % 60].map(value => String(value).padStart(2, "0")).join(":");
}

function renderHand(side, enabled, actual = [], target = [], speeds = []) {
  const panel = $(`#${side}-panel`);
  const state = $('.hand-state', panel);
  state.textContent = enabled ? t("connected") : t("disabled");
  state.classList.toggle("disabled", !enabled);
  const list = $('.joint-list', panel);
  list.innerHTML = copy[language].jointNames.map((name, index) => {
    const actualValue = Math.max(0, Math.min(1, Number(actual[index] || 0)));
    const targetValue = Math.max(0, Math.min(1, Number(target[index] || 0)));
    const speed = String(Math.round(speeds[index] || 0)).padStart(4, "0");
    return `<div class="joint-row"><span class="joint-name">${name}</span><div><div class="joint-values"><span>${actualValue.toFixed(2)}</span><b>${targetValue.toFixed(2)}</b></div><div class="joint-track"><span class="joint-actual" style="width:${actualValue * 100}%"></span><i class="joint-target" style="left:${targetValue * 100}%"></i></div></div><span class="joint-speed">${speed}</span></div>`;
  }).join("");
}

function renderSnapshot(snapshot) {
  if (!snapshot) return;
  latestSnapshot = snapshot;
  $('#session-time').textContent = formatDuration(snapshot.elapsed_seconds);
  $('#loop-rate').textContent = Number(snapshot.loop_hz || 0).toFixed(1);
  $('#speed-mode-label').textContent = t(snapshot.speed_mode);
  const motionFilterEnabled = Boolean(snapshot.motion_filter_enabled);
  const motionFilterButton = $('#motion-filter-button');
  motionFilterButton.classList.toggle("toggle-active", motionFilterEnabled);
  motionFilterButton.setAttribute("aria-pressed", String(motionFilterEnabled));
  $('span', motionFilterButton).textContent = t(
    motionFilterEnabled ? "motionFilterOn" : "motionFilterOff"
  );
  const running = snapshot.tracking_enabled && snapshot.motion_data_ready;
  const trackingEnabled = Boolean(snapshot.tracking_enabled);
  $('#tracking-indicator').classList.toggle("running", running);
  $('#tracking-label').textContent = running ? t("running") : trackingEnabled ? t("waitingData") : t("paused");
  $('#tracking-detail').textContent = trackingEnabled ? (snapshot.motion_data_ready ? t("ready") : t("waitingData")) : t("paused");
  $('#quest-label').textContent = snapshot.motion_data_ready ? t("ready") : t("unavailable");
  const trackingButton = $('#tracking-button');
  trackingButton.classList.toggle("stop-button", trackingEnabled);
  trackingButton.dataset.action = trackingEnabled ? "pause" : "run";
  $('span:last-child', trackingButton).textContent = t(trackingEnabled ? "stopTracking" : "run");
  $('span:first-child', trackingButton).className = trackingEnabled ? "stop-icon" : "play-icon";
  renderHand("left", snapshot.left_enabled, snapshot.left_state, snapshot.left_target, snapshot.left_speed);
  renderHand("right", snapshot.right_enabled, snapshot.right_state, snapshot.right_target, snapshot.right_speed);
}

function tactileFrameCopy(regions = {}) {
  return Object.fromEntries(Object.entries(regions).map(([name, rows]) => [
    name,
    Array.isArray(rows) ? rows.map(row => Array.isArray(row) ? row.map(value => Number(value) || 0) : []) : []
  ]));
}

function tactileQuantile(values, probability) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const position = Math.max(0, Math.min(sorted.length - 1, probability * (sorted.length - 1)));
  const lowerIndex = Math.floor(position);
  const upperIndex = Math.ceil(position);
  const fraction = position - lowerIndex;
  return sorted[lowerIndex] + (sorted[upperIndex] - sorted[lowerIndex]) * fraction;
}

function clearTactileTemporalState() {
  tactileFilter.temporal = {};
  tactileFilter.moduleStates = {};
  tactileFilter.displayCache = {};
  tactileFilter.displayRevisions = {};
  tactileFingerprint = "";
}

function resetTactileFilter(messageKey = "filterReadyHint") {
  if (tactileFilter.timer) window.clearTimeout(tactileFilter.timer);
  tactileFilter = createTactileFilterState();
  tactileFilter.messageKey = messageKey;
  tactileFingerprint = "";
  renderTactileFilterPanel();
}

function selectedTactileHandsReady() {
  const hands = latestSnapshot?.tactile?.hands || {};
  return tactileSelection.length > 0 && tactileSelection.every(side => Object.keys(hands[side]?.regions || {}).length > 0);
}

function beginTactileBaselineLearning() {
  if (tactileFilter.status === "calibrating") {
    if (tactileFilter.timer) window.clearTimeout(tactileFilter.timer);
    tactileFilter.status = "idle";
    tactileFilter.samples = {};
    tactileFilter.sampleRevisions = {};
    tactileFilter.messageKey = "filterReadyHint";
    renderTactileFilterPanel();
    return;
  }
  if (!selectedTactileHandsReady()) {
    tactileFilter.status = "error";
    tactileFilter.messageKey = "filterSelectHand";
    renderTactileFilterPanel();
    return;
  }
  tactileFilter.status = "calibrating";
  tactileFilter.sides = [...tactileSelection];
  tactileFilter.startedAt = performance.now();
  tactileFilter.samples = Object.fromEntries(tactileFilter.sides.map(side => [side, []]));
  tactileFilter.sampleRevisions = {};
  tactileFilter.messageKey = "filterKeepStill";
  clearTactileTemporalState();
  renderTactileFilterPanel();
  tactileFilter.timer = window.setTimeout(finishTactileBaselineLearning, tactileCalibrationDurationMs + 80);
}

function collectTactileBaselineSamples(hands = {}) {
  if (tactileFilter.status !== "calibrating") return;
  tactileFilter.sides.forEach(side => {
    const hand = hands[side];
    const revision = Number(hand?.revision || 0);
    if (!revision || revision === tactileFilter.sampleRevisions[side]) return;
    const regions = hand?.regions || {};
    if (!Object.keys(regions).length) return;
    tactileFilter.sampleRevisions[side] = revision;
    tactileFilter.samples[side].push({
      regions: tactileFrameCopy(regions),
      forces: Array.isArray(hand.forces) ? hand.forces.map(value => Number(value) || 0) : []
    });
  });
  renderTactileFilterPanel();
}

function finishTactileBaselineLearning() {
  if (tactileFilter.status !== "calibrating") return;
  tactileFilter.timer = null;
  const complete = tactileFilter.sides.every(side => (tactileFilter.samples[side] || []).length >= tactileCalibrationMinimumSamples);
  if (!complete) {
    tactileFilter.status = "error";
    tactileFilter.messageKey = "filterNotEnoughSamples";
    renderTactileFilterPanel();
    return;
  }

  tactileFilter.sides.forEach(side => {
    const frames = tactileFilter.samples[side];
    const reference = frames[0].regions;
    const baselines = {};
    const deadbands = {};
    Object.entries(reference).forEach(([name, rows]) => {
      baselines[name] = rows.map((row, rowIndex) => row.map((_value, columnIndex) => {
        const values = frames.map(frame => Number(frame.regions[name]?.[rowIndex]?.[columnIndex]) || 0);
        return tactileQuantile(values, 0.5);
      }));
      deadbands[name] = rows.map((row, rowIndex) => row.map((_value, columnIndex) => {
        const values = frames.map(frame => Number(frame.regions[name]?.[rowIndex]?.[columnIndex]) || 0);
        const baseline = baselines[name][rowIndex][columnIndex];
        const deviations = values.map(value => Math.abs(value - baseline));
        return Math.max(3, tactileQuantile(deviations, 0.99) + 2);
      }));
    });
    tactileFilter.baselines[side] = baselines;
    tactileFilter.modeBaselines.basic[side] = tactileFrameCopy(baselines);
    tactileFilter.modeBaselines.enhanced[side] = tactileFrameCopy(baselines);
    tactileFilter.deadbands[side] = deadbands;
    const forceFrames = frames.map(frame => frame.forces).filter(values => values.length === 6);
    if (forceFrames.length >= tactileCalibrationMinimumSamples) {
      tactileFilter.forceBaselines[side] = Array.from({ length: 6 }, (_unused, index) => {
        return tactileQuantile(forceFrames.map(values => values[index]), 0.5);
      });
      tactileFilter.forceDeadbands[side] = Array.from({ length: 6 }, (_unused, index) => {
        const baseline = tactileFilter.forceBaselines[side][index];
        const deviations = forceFrames.map(values => Math.abs(values[index] - baseline));
        return Math.max(5, tactileQuantile(deviations, 0.99) + 3);
      });
    } else {
      delete tactileFilter.forceBaselines[side];
      delete tactileFilter.forceDeadbands[side];
    }
    tactileFilter.calibratedSides.add(side);
  });
  tactileFilter.status = "ready";
  tactileFilter.samples = {};
  tactileFilter.sampleRevisions = {};
  tactileFilter.messageKey = tactileFilter.sides.every(side => tactileFilter.forceBaselines[side]?.length === 6)
    ? "filterComplete"
    : "filterCompleteNoForce";
  tactileDisplayMode = "filtered";
  clearTactileTemporalState();
  renderTactileFilterPanel();
}

function tactileFilterStatus() {
  if (tactileFilter.status === "calibrating" || tactileFilter.status === "error") return tactileFilter.status;
  if (!tactileFilter.calibratedSides.size) return "idle";
  if (tactileSelection.length && tactileSelection.every(side => tactileFilter.calibratedSides.has(side))) return "ready";
  return "partial";
}

function renderTactileFilterPanel() {
  const panel = $('#filter-state');
  if (!panel) return;
  const status = tactileFilterStatus();
  panel.dataset.state = status;
  $('span:last-child', panel).textContent = t({
    idle: "filterUncalibrated",
    calibrating: "filterCalibrating",
    ready: "filterCalibrated",
    partial: "filterIncomplete",
    error: "filterFailed"
  }[status]);

  const elapsed = tactileFilter.status === "calibrating" ? performance.now() - tactileFilter.startedAt : 0;
  const progress = tactileFilter.status === "calibrating" ? Math.min(100, elapsed / tactileCalibrationDurationMs * 100) : status === "ready" ? 100 : 0;
  $('#filter-progress-bar').style.width = `${progress}%`;
  $('#filter-progress-label').textContent = t(tactileFilter.messageKey);
  $('#filter-point-count').textContent = tactileFilter.pointCount.toLocaleString(language === "zh" ? "zh-CN" : "en-US");
  $('#filter-active-count').textContent = tactileFilter.activeCount === null ? "--" : tactileFilter.activeCount;
  $('#filter-suppressed-count').textContent = tactileFilter.suppressedCount === null ? "--" : tactileFilter.suppressedCount;
  const moduleCounts = tactileFilter.moduleStateCounts;
  $('#filter-module-state').textContent = moduleCounts === null
    ? "--"
    : `${t("filterNoContactShort")} ${moduleCounts.no_contact} · ${t("filterContactShort")} ${moduleCounts.contact} · ${t("filterRecoveryShort")} ${moduleCounts.recovery}`;
  $('.filter-module-metric')?.classList.toggle("inactive", tactileProcessingMode !== "enhanced");

  const driftLabelKey = tactileProcessingMode === "enhanced" ? "filterDrift" : "filterBasicDrift";
  const driftHelpKey = tactileProcessingMode === "enhanced" ? "filterDriftHelp" : "filterBasicDriftHelp";
  const driftLabel = $('#filter-drift-label');
  const driftHelp = $('#filter-drift-help');
  driftLabel.dataset.i18n = driftLabelKey;
  driftHelp.dataset.i18n = driftHelpKey;
  driftLabel.textContent = t(driftLabelKey);
  driftHelp.textContent = t(driftHelpKey);

  const button = $('#tactile-zero-button');
  button.disabled = tactileFilter.status !== "calibrating" && !selectedTactileHandsReady();
  $('span:last-child', button).textContent = t(tactileFilter.status === "calibrating" ? "filterCancel" : tactileFilter.calibratedSides.size ? "filterRecalibrate" : "filterCalibrate");
  button.classList.toggle("calibrating", tactileFilter.status === "calibrating");
  $$('#tactile-display-selector button').forEach(option => {
    const active = option.dataset.tactileDisplay === tactileDisplayMode;
    option.classList.toggle("active", active);
    option.setAttribute("aria-pressed", active ? "true" : "false");
  });
  $$('#tactile-processing-selector button').forEach(option => {
    const active = option.dataset.tactileProcessing === tactileProcessingMode;
    option.classList.toggle("active", active);
    option.setAttribute("aria-pressed", active ? "true" : "false");
    option.disabled = tactileFilter.status === "calibrating";
  });
}

function tactileTemporalRegion(side, name, rows) {
  tactileFilter.temporal[side] ||= {};
  const existing = tactileFilter.temporal[side][name];
  if (existing && existing.history.length === rows.length && existing.history.every((row, index) => row.length === rows[index].length)) return existing;
  const region = {
    history: rows.map(row => row.map(() => [0, 0])),
    smoothed: rows.map(row => row.map(() => 0)),
    active: rows.map(row => row.map(() => false))
  };
  tactileFilter.temporal[side][name] = region;
  return region;
}

function tactileModuleState(side, name) {
  tactileFilter.moduleStates[side] ||= {};
  tactileFilter.moduleStates[side][name] ||= {
    state: "no_contact",
    peakResponse: 0,
    lastResponse: 0,
    quietSince: null,
    lastAt: performance.now()
  };
  return tactileFilter.moduleStates[side][name];
}

function tactileRegionForceChannel(name) {
  const finger = String(name).split("_", 1)[0];
  return Object.prototype.hasOwnProperty.call(tactileForceIndex, finger) ? tactileForceIndex[finger] : null;
}

function tactileLargestComponent(mask) {
  const visited = mask.map(row => row.map(() => false));
  let largest = 0;
  mask.forEach((row, rowIndex) => row.forEach((active, columnIndex) => {
    if (!active || visited[rowIndex][columnIndex]) return;
    let size = 0;
    const pending = [[rowIndex, columnIndex]];
    visited[rowIndex][columnIndex] = true;
    while (pending.length) {
      const [currentRow, currentColumn] = pending.pop();
      size += 1;
      [[currentRow - 1, currentColumn], [currentRow + 1, currentColumn], [currentRow, currentColumn - 1], [currentRow, currentColumn + 1]].forEach(([nextRow, nextColumn]) => {
        if (nextRow < 0 || nextColumn < 0 || nextRow >= mask.length || nextColumn >= mask[nextRow].length) return;
        if (!mask[nextRow][nextColumn] || visited[nextRow][nextColumn]) return;
        visited[nextRow][nextColumn] = true;
        pending.push([nextRow, nextColumn]);
      });
    }
    largest = Math.max(largest, size);
  }));
  return largest;
}

function processBasicTactileHand(side, hand) {
  const revision = Number(hand?.revision || 0);
  if (revision && tactileFilter.displayRevisions[side] === revision && tactileFilter.displayCache[side]) return tactileFilter.displayCache[side];
  if (!tactileFilter.calibratedSides.has(side) || !Object.keys(hand?.regions || {}).length) return hand;

  const sensitivity = $('#tactile-filter-sensitivity')?.value || "balanced";
  const profile = tactileSensitivityProfiles[sensitivity] || tactileSensitivityProfiles.balanced;
  const compensateDrift = Boolean($('#tactile-drift-compensation')?.checked);
  let activeCount = 0;
  let suppressedCount = 0;
  const regions = Object.fromEntries(Object.entries(hand.regions).map(([name, rows]) => {
    const baselineRows = tactileFilter.modeBaselines.basic[side]?.[name] || [];
    const deadbandRows = tactileFilter.deadbands[side]?.[name] || [];
    const temporal = tactileTemporalRegion(side, name, rows);
    const output = rows.map((row, rowIndex) => row.map((rawValue, columnIndex) => {
      const raw = Math.max(0, Math.min(4095, Number(rawValue) || 0));
      const baseline = Number(baselineRows[rowIndex]?.[columnIndex] || 0);
      const threshold = Math.max(3, Number(deadbandRows[rowIndex]?.[columnIndex] || 3) * profile.thresholdScale);
      const residual = Math.max(0, raw - baseline);
      const history = temporal.history[rowIndex][columnIndex];
      history.push(residual);
      if (history.length > 3) history.shift();
      const medianResidual = history[0] + history[1] + history[2] - Math.min(...history) - Math.max(...history);
      const wasActive = temporal.active[rowIndex][columnIndex];
      const contact = medianResidual > threshold * (wasActive ? 0.6 : 1);
      temporal.active[rowIndex][columnIndex] = contact;
      const gated = contact ? medianResidual : 0;
      const previous = temporal.smoothed[rowIndex][columnIndex];
      let filtered = previous + profile.smoothing * (gated - previous);
      if (gated === 0 && filtered < 1) filtered = 0;
      filtered = Math.max(0, Math.min(4095, Math.round(filtered)));
      temporal.smoothed[rowIndex][columnIndex] = filtered;
      if (contact) activeCount += 1;
      if (residual > 0 && !contact) suppressedCount += 1;
      if (compensateDrift && raw - baseline <= threshold) {
        baselineRows[rowIndex][columnIndex] = baseline + (raw - baseline) * 0.0015;
      }
      return filtered;
    }));
    return [name, output];
  }));
  const filteredHand = { ...hand, regions, raw_regions: hand.regions, filter_stats: { mode: "basic", activeCount, suppressedCount } };
  tactileFilter.displayRevisions[side] = revision;
  tactileFilter.displayCache[side] = filteredHand;
  return filteredHand;
}

function processEnhancedTactileHand(side, hand) {
  const revision = Number(hand?.revision || 0);
  if (revision && tactileFilter.displayRevisions[side] === revision && tactileFilter.displayCache[side]) return tactileFilter.displayCache[side];
  if (!tactileFilter.calibratedSides.has(side) || !Object.keys(hand?.regions || {}).length) return hand;

  const sensitivity = $('#tactile-filter-sensitivity')?.value || "balanced";
  const profile = tactileSensitivityProfiles[sensitivity] || tactileSensitivityProfiles.balanced;
  const compensateDrift = Boolean($('#tactile-drift-compensation')?.checked);
  const frameNow = performance.now();
  const forceValues = Array.isArray(hand.forces) ? hand.forces.map(value => Number(value) || 0) : [];
  const forceAge = Number(hand.force_age_seconds);
  let activeCount = 0;
  let suppressedCount = 0;
  const moduleStates = { no_contact: 0, contact: 0, recovery: 0 };
  const regions = Object.fromEntries(Object.entries(hand.regions).map(([name, rows]) => {
    const baselineRows = tactileFilter.modeBaselines.enhanced[side]?.[name] || [];
    const deadbandRows = tactileFilter.deadbands[side]?.[name] || [];
    const temporal = tactileTemporalRegion(side, name, rows);
    const rawRows = rows.map(row => row.map(rawValue => Math.max(0, Math.min(4095, Number(rawValue) || 0))));
    const thresholdRows = rows.map((row, rowIndex) => row.map((_value, columnIndex) => {
      return Math.max(3, Number(deadbandRows[rowIndex]?.[columnIndex] || 3) * profile.thresholdScale);
    }));

    const calculateModuleSignal = () => {
      const deltas = rawRows.map((row, rowIndex) => row.map((raw, columnIndex) => {
        return raw - Number(baselineRows[rowIndex]?.[columnIndex] || 0);
      }));
      const commonCandidates = [];
      deltas.forEach((row, rowIndex) => row.forEach((delta, columnIndex) => {
        if (Math.abs(delta) <= thresholdRows[rowIndex][columnIndex]) commonCandidates.push(delta);
      }));
      const common = commonCandidates.length ? tactileQuantile(commonCandidates, 0.5) : 0;
      const residuals = deltas.map(row => row.map(delta => Math.max(0, delta - common)));
      const activeMask = residuals.map((row, rowIndex) => row.map((residual, columnIndex) => {
        return residual > thresholdRows[rowIndex][columnIndex];
      }));
      const flatResiduals = residuals.flat();
      return {
        common,
        deltas,
        residuals,
        activeMask,
        response: flatResiduals.reduce((total, value) => total + value, 0),
        maximum: Math.max(0, ...flatResiduals),
        largestComponent: tactileLargestComponent(activeMask)
      };
    };

    let signal = calculateModuleSignal();
    const forceChannel = tactileRegionForceChannel(name);
    const forceBaseline = forceChannel === null ? null : tactileFilter.forceBaselines[side]?.[forceChannel];
    const forceDeadband = forceChannel === null ? null : tactileFilter.forceDeadbands[side]?.[forceChannel];
    const forceAvailable = forceChannel !== null && forceValues.length === 6 && forceBaseline !== undefined && forceDeadband !== undefined && Number.isFinite(forceAge) && forceAge <= 0.5;
    const forceContact = forceAvailable && Math.abs(forceValues[forceChannel] - forceBaseline) > forceDeadband;
    const strongSinglePoint = signal.maximum > Math.max(20, Math.max(...thresholdRows.flat()) * 4);
    const tactileContact = signal.largestComponent >= 2 || strongSinglePoint;
    const module = tactileModuleState(side, name);
    const elapsedSeconds = Math.max(0.001, Math.min(0.5, (frameNow - module.lastAt) / 1000));
    module.lastAt = frameNow;

    if (module.state === "no_contact") {
      if (forceContact || tactileContact) {
        module.state = "contact";
        module.peakResponse = signal.response;
        module.quietSince = null;
      }
    } else if (module.state === "contact") {
      module.peakResponse = Math.max(module.peakResponse, signal.response);
      const unloadedAfterPeak = module.peakResponse > 80 && signal.response < Math.max(20, module.peakResponse * 0.3);
      const unloadedWithoutTactile = module.peakResponse <= 80 && !tactileContact;
      const forceConfirmedRecovery = compensateDrift && forceAvailable && !forceContact && unloadedAfterPeak;
      const cleanRelease = (forceAvailable && !forceContact && unloadedWithoutTactile) || (!forceAvailable && !tactileContact);
      if (forceConfirmedRecovery || cleanRelease) {
        module.quietSince ??= frameNow;
        if ((frameNow - module.quietSince) / 1000 >= tactileRecoveryConfirmSeconds) {
          module.state = forceConfirmedRecovery ? "recovery" : "no_contact";
          if (module.state === "no_contact") module.peakResponse = 0;
          module.quietSince = null;
        }
      } else {
        module.quietSince = null;
      }
    } else {
      const risingAgain = tactileContact && signal.response > Math.max(80, module.lastResponse * 1.8);
      if (forceContact || risingAgain) {
        module.state = "contact";
        module.peakResponse = signal.response;
        module.quietSince = null;
      }
    }

    if (compensateDrift && module.state !== "contact") {
      const tauSeconds = module.state === "recovery" ? tactileRecoveryTauSeconds : tactileBaselineTauSeconds;
      const baselineAlpha = 1 - Math.exp(-elapsedSeconds / tauSeconds);
      rawRows.forEach((row, rowIndex) => row.forEach((raw, columnIndex) => {
        const baseline = Number(baselineRows[rowIndex]?.[columnIndex] || 0);
        const smallIdleChange = raw - baseline - signal.common <= thresholdRows[rowIndex][columnIndex];
        if (module.state === "recovery" || smallIdleChange) {
          baselineRows[rowIndex][columnIndex] = baseline + baselineAlpha * (raw - baseline);
        }
      }));
      signal = calculateModuleSignal();
      const recovered = signal.activeMask.every(row => row.every(active => !active));
      if (module.state === "recovery" && recovered) {
        module.state = "no_contact";
        module.peakResponse = 0;
      }
    }
    module.lastResponse = signal.response;
    moduleStates[module.state] += 1;

    const output = rows.map((row, rowIndex) => row.map((_rawValue, columnIndex) => {
      const threshold = thresholdRows[rowIndex][columnIndex];
      const residual = signal.residuals[rowIndex][columnIndex];
      const history = temporal.history[rowIndex][columnIndex];
      history.push(residual);
      if (history.length > 3) history.shift();
      const medianResidual = history[0] + history[1] + history[2] - Math.min(...history) - Math.max(...history);
      const wasActive = temporal.active[rowIndex][columnIndex];
      const contact = medianResidual > threshold * (wasActive ? 0.6 : 1);
      temporal.active[rowIndex][columnIndex] = contact;
      const gated = contact ? medianResidual : 0;
      const previous = temporal.smoothed[rowIndex][columnIndex];
      let filtered = previous + profile.smoothing * (gated - previous);
      if (gated === 0 && filtered < 1) filtered = 0;
      filtered = Math.max(0, Math.min(4095, Math.round(filtered)));
      temporal.smoothed[rowIndex][columnIndex] = filtered;
      if (contact) activeCount += 1;
      if (residual > 0 && !contact) suppressedCount += 1;
      return filtered;
    }));
    return [name, output];
  }));
  const filteredHand = { ...hand, regions, raw_regions: hand.regions, filter_stats: { mode: "enhanced", activeCount, suppressedCount, moduleStates } };
  tactileFilter.displayRevisions[side] = revision;
  tactileFilter.displayCache[side] = filteredHand;
  return filteredHand;
}

function processTactileHand(side, hand) {
  return tactileProcessingMode === "basic"
    ? processBasicTactileHand(side, hand)
    : processEnhancedTactileHand(side, hand);
}

function tactileDisplayHands(hands = {}) {
  let activeCount = 0;
  let suppressedCount = 0;
  const moduleStateCounts = { no_contact: 0, contact: 0, recovery: 0 };
  const processed = Object.fromEntries(Object.entries(hands).map(([side, hand]) => {
    const filtered = processTactileHand(side, hand);
    if (filtered !== hand) {
      activeCount += Number(filtered.filter_stats?.activeCount || 0);
      suppressedCount += Number(filtered.filter_stats?.suppressedCount || 0);
      if (tactileProcessingMode === "enhanced") {
        Object.keys(moduleStateCounts).forEach(state => {
          moduleStateCounts[state] += Number(filtered.filter_stats?.moduleStates?.[state] || 0);
        });
      }
    }
    return [side, tactileDisplayMode === "filtered" ? filtered : hand];
  }));
  if (tactileFilter.calibratedSides.size) {
    tactileFilter.pointCount = Object.values(tactileFilter.baselines).reduce((total, regions) => total + Object.values(regions).flat(2).length, 0);
    tactileFilter.activeCount = activeCount;
    tactileFilter.suppressedCount = suppressedCount;
    tactileFilter.moduleStateCounts = tactileProcessingMode === "enhanced" ? moduleStateCounts : null;
  }
  renderTactileFilterPanel();
  return processed;
}

function tactileHeatColor(value) {
  const ratio = Math.max(0, Math.min(1, Number(value || 0) / 4095));
  const stops = [
    [0, [20, 25, 33]],
    [0.2, [31, 80, 125]],
    [0.45, [27, 170, 145]],
    [0.7, [239, 193, 58]],
    [1, [240, 71, 69]]
  ];
  const upperIndex = Math.max(1, stops.findIndex(stop => ratio <= stop[0]));
  const lower = stops[upperIndex - 1];
  const upper = stops[upperIndex];
  const progress = (ratio - lower[0]) / (upper[0] - lower[0] || 1);
  const rgb = lower[1].map((channel, index) => Math.round(channel + (upper[1][index] - channel) * progress));
  return `rgb(${rgb.join(",")})`;
}

function tactilePointDescription(label, rowIndex, columnIndex, value, rawValue = null) {
  const reading = rawValue === null
    ? `${t("sensorValue")} ${value}`
    : `${t("processedValue")} ${value} · ${t("rawValue")} ${rawValue}`;
  return `${label} · ${t("row")} ${rowIndex + 1} · ${t("column")} ${columnIndex + 1} · ${reading}`;
}

function tactileRegionMarkup(name, values, rawValues = null) {
  const rows = Array.isArray(values) ? values : [];
  const columns = rows.length && Array.isArray(rows[0]) ? rows[0].length : 0;
  if (!rows.length || !columns) return "";
  const label = copy[language].tactileRegions[name] || name;
  const displayRows = rows.map((row, rowIndex) => ({ row, rowIndex }));
  if (name === "palm") displayRows.reverse();
  const cells = displayRows.flatMap(({ row, rowIndex }) => row.map((sourceValue, columnIndex) => {
    const value = Math.max(0, Math.min(4095, Number(sourceValue) || 0));
    const rawReading = rawValues === null ? null : Math.max(0, Math.min(4095, Number(rawValues?.[rowIndex]?.[columnIndex]) || 0));
    const description = tactilePointDescription(label, rowIndex, columnIndex, value, rawReading);
    return `<span class="tactile-cell" style="--cell-color:${tactileHeatColor(value)}" data-row="${rowIndex}" data-column="${columnIndex}" data-tooltip="${escapeHtml(description)}"></span>`;
  })).join("");
  return `<section class="tactile-region" data-region="${name}"><header><strong>${escapeHtml(label)}</strong><span>${rows.length} × ${columns}</span></header><div class="tactile-matrix" style="--tactile-columns:${columns}">${cells}</div></section>`;
}

function tactileHandMarkup(side, hand) {
  const sideLabel = t(side === "left" ? "leftHand" : "rightHand");
  const regions = hand?.regions || {};
  if (hand?.error && !Object.keys(regions).length) {
    return `<article class="tactile-hand console-card" data-side="${side}"><div class="tactile-hand-heading"><span class="hand-avatar">${side === "left" ? "L" : "R"}</span><div><h2>${escapeHtml(sideLabel)}</h2><p class="tactile-error-text">${escapeHtml(hand.error)}</p></div></div><div class="tactile-empty error"><span>!</span><strong>${escapeHtml(t("tactileError"))}</strong></div></article>`;
  }
  if (!Object.keys(regions).length) {
    return `<article class="tactile-hand console-card" data-side="${side}"><div class="tactile-hand-heading"><span class="hand-avatar">${side === "left" ? "L" : "R"}</span><div><h2>${escapeHtml(sideLabel)}</h2><p>${escapeHtml(t("waitingTactile"))}</p></div></div><div class="tactile-empty"><span class="tactile-loader"></span><strong>${escapeHtml(t("tactileNoData"))}</strong></div></article>`;
  }
  const fingerGroups = tactileGroupSpecs.filter(([groupName]) => groupName !== "palm");
  const palmGroups = tactileGroupSpecs.filter(([groupName]) => groupName === "palm");
  const displayGroups = side === "left"
    ? [...fingerGroups].reverse().concat(palmGroups)
    : fingerGroups.concat(palmGroups);
  const groups = displayGroups.map(([groupName, regionNames]) => {
    const regionMarkup = regionNames.map(name => tactileRegionMarkup(name, regions[name], hand?.raw_regions?.[name] || null)).filter(Boolean).join("");
    if (!regionMarkup) return "";
    return `<section class="tactile-digit ${groupName === "palm" ? "palm" : ""}"><h3>${escapeHtml(copy[language].tactileGroups[groupName])}</h3><div>${regionMarkup}</div></section>`;
  }).join("");
  return `<article class="tactile-hand console-card" data-side="${side}"><div class="tactile-hand-heading"><span class="hand-avatar">${side === "left" ? "L" : "R"}</span><div><h2>${escapeHtml(sideLabel)}</h2><p>${escapeHtml(t("tactileReady"))}</p></div><span class="hand-state">${escapeHtml(t("connected"))}</span></div><div class="tactile-regions">${groups}</div></article>`;
}

function updateTactileCells(selection, hands) {
  const renderedSides = $$('.tactile-hand', $('#tactile-hands')).map(element => element.dataset.side);
  if (renderedSides.join(",") !== selection.join(",")) return false;
  const updates = [];
  for (const side of selection) {
    const handElement = $(`.tactile-hand[data-side="${side}"]`, $('#tactile-hands'));
    const regions = hands[side]?.regions || {};
    if (!handElement || !Object.keys(regions).length) return false;
    for (const [name, rows] of Object.entries(regions)) {
      const regionElement = $(`.tactile-region[data-region="${name}"]`, handElement);
      const columns = Array.isArray(rows) && rows.length && Array.isArray(rows[0]) ? rows[0].length : 0;
      const cells = regionElement ? $$('.tactile-cell', regionElement) : [];
      const valueCount = Array.isArray(rows) ? rows.reduce((total, row) => total + (Array.isArray(row) ? row.length : 0), 0) : 0;
      if (!columns || cells.length !== valueCount) return false;
      const label = copy[language].tactileRegions[name] || name;
      const rawRows = hands[side]?.raw_regions?.[name] || null;
      cells.forEach(cell => {
        const rowIndex = Number(cell.dataset.row);
        const columnIndex = Number(cell.dataset.column);
        const value = Math.max(0, Math.min(4095, Number(rows[rowIndex]?.[columnIndex]) || 0));
        const rawValue = rawRows === null ? null : Math.max(0, Math.min(4095, Number(rawRows?.[rowIndex]?.[columnIndex]) || 0));
        updates.push({ cell, color: tactileHeatColor(value), description: tactilePointDescription(label, rowIndex, columnIndex, value, rawValue) });
      });
    }
  }
  updates.forEach(({ cell, color, description }) => {
    cell.style.setProperty("--cell-color", color);
    cell.dataset.tooltip = description;
  });
  if (activeTactileCell?.isConnected && !$('#tactile-tooltip').hidden) {
    $('#tactile-tooltip').textContent = activeTactileCell.dataset.tooltip;
  }
  return true;
}

function renderTactile(tactile = {}) {
  if (activeNav !== "tactile") return;
  const enabledSides = ["left", "right"].filter(side => latestSnapshot?.[`${side}_enabled`]);
  const selection = Array.isArray(tactile.selection) && tactile.selection.length ? tactile.selection : tactileSelection;
  tactileSelection = selection.filter(side => enabledSides.includes(side));
  if (!tactileSelection.length && enabledSides.length) {
    setTactileSelection(enabledSides);
    return;
  }
  const singleHand = enabledSides.length === 1;
  $$('#tactile-side-selector button').forEach(button => {
    const buttonSides = button.dataset.tactileSides.split(",");
    const available = buttonSides.every(side => enabledSides.includes(side)) && (!singleHand || buttonSides.length === 1);
    button.hidden = !available;
    button.classList.toggle("active", button.dataset.tactileSides === tactileSelection.join(","));
    button.setAttribute("aria-pressed", button.classList.contains("active") ? "true" : "false");
  });
  const sampleRate = Number(tactile.sample_hz || tactile.target_hz || 0);
  $('#tactile-rate').textContent = sampleRate > 0
    ? `${sampleRate.toFixed(sampleRate >= 10 ? 0 : 1)} Hz`
    : "--";

  const rawHands = tactile.hands || {};
  collectTactileBaselineSamples(rawHands);
  const hands = tactileDisplayHands(rawHands);
  const hasError = tactileSelection.some(side => rawHands[side]?.error);
  const ready = tactileSelection.length > 0 && tactileSelection.every(side => Object.keys(rawHands[side]?.regions || {}).length > 0);
  const status = $('#tactile-status');
  status.textContent = t(hasError ? "tactileError" : ready ? "tactileReady" : "waitingTactile");
  $('.tactile-live-state .status-dot').className = `status-dot ${hasError ? "error" : ready ? "live" : ""}`;

  const fingerprint = `${language}|${tactileDisplayMode}|${tactileProcessingMode}|${tactileSelection.join(",")}|${tactileSelection.map(side => `${side}:${hands[side]?.revision || 0}:${hands[side]?.error || ""}`).join("|")}`;
  if (fingerprint === tactileFingerprint) return;
  tactileFingerprint = fingerprint;
  const container = $('#tactile-hands');
  container.classList.toggle("single", tactileSelection.length === 1);
  if (updateTactileCells(tactileSelection, hands)) return;
  activeTactileCell = null;
  $('#tactile-tooltip').hidden = true;
  container.innerHTML = tactileSelection.map(side => tactileHandMarkup(side, hands[side])).join("");
}

function captureStateLabel(state) {
  return t({
    idle: "captureIdle",
    recording: "captureRecording",
    stopping: "captureStopping",
    completed: "captureCompleted",
    stopped: "captureStopped",
    error: "captureFailed"
  }[state] || "captureIdle");
}

function renderTactileCapture(capture = { state: "idle" }) {
  const wasActive = ["recording", "stopping"].includes(latestCapture.state);
  latestCapture = capture || { state: "idle" };
  const state = latestCapture.state || "idle";
  const active = state === "recording" || state === "stopping";
  const stateElement = $('#capture-state');
  stateElement.dataset.state = state;
  $('span:last-child', stateElement).textContent = captureStateLabel(state);

  const form = $('#tactile-capture-form');
  $$('input', form).forEach(input => { input.disabled = active; });
  $('#capture-start').hidden = active;
  $('#capture-stop').hidden = !active;
  $('#capture-stop').disabled = state === "stopping";
  $$('#tactile-side-selector button').forEach(button => { button.disabled = active || tactileFilter.status === "calibrating"; });

  const tactileRate = Number(latestSnapshot?.tactile?.target_hz || latestConfig.tactile_frequency || 60);
  const mainRate = Number(latestConfig.frequency || 60);
  const maximumRate = Math.max(0.1, Math.min(60, tactileRate || 60, mainRate || 60));
  const frequencyInput = form.elements.capture_frequency;
  frequencyInput.max = String(Number(maximumRate.toFixed(1)));
  if (!active && Number(frequencyInput.value) > maximumRate) frequencyInput.value = maximumRate.toFixed(maximumRate >= 1 ? 1 : 2);
  $('#capture-frequency-hint').textContent = `${t("captureFrequencyHint")} · ≤ ${maximumRate.toFixed(maximumRate >= 10 ? 0 : 1)} Hz`;

  const elapsed = Number(latestCapture.elapsed_seconds || 0);
  const duration = Number(latestCapture.duration_seconds || form.elements.capture_duration.value || 0);
  const progress = duration > 0 ? Math.max(0, Math.min(100, elapsed / duration * 100)) : 0;
  $('#capture-progress-bar').style.width = `${state === "completed" ? 100 : progress}%`;
  $('#capture-sample-count').textContent = Number(latestCapture.sample_count || 0);
  $('#capture-progress-label').textContent = state === "idle"
    ? t("captureWaiting")
    : `${t("captureProgress")} · ${elapsed.toFixed(1)} / ${duration.toFixed(1)} s`;

  const details = [];
  if (latestCapture.path) details.push(`${t("captureSavedTo")}: ${latestCapture.path}`);
  if (Number(latestCapture.dropped_count || 0) > 0) details.push(`${t("captureDropped")}: ${latestCapture.dropped_count}`);
  $('#capture-result').textContent = details.join(" · ");
  $('#capture-result').title = latestCapture.path || "";
  $('#capture-error').textContent = latestCapture.error || captureRequestError;
  if (wasActive && !active && activeNav !== "tactile" && lastPhase === "live") stopTactileSampling();
}

async function setTactileSelection(requestedSides) {
  if (["recording", "stopping"].includes(latestCapture.state) || tactileFilter.status === "calibrating") return;
  const enabledSides = ["left", "right"].filter(side => latestSnapshot?.[`${side}_enabled`]);
  if (!enabledSides.length) return;
  const nextSelection = enabledSides.length === 1
    ? enabledSides
    : ["left", "right"].filter(side => requestedSides.includes(side) && enabledSides.includes(side));
  tactileSelection = nextSelection;
  tactileFingerprint = "";
  const targetRate = Number(latestSnapshot?.tactile?.target_hz || 0);
  renderTactile({ sample_hz: targetRate, target_hz: targetRate, selection: nextSelection, hands: {} });
  try {
    const result = await post("/api/tactile", { sides: nextSelection });
    tactileSelection = result.sides || nextSelection;
    renderTactileFilterPanel();
  } catch (error) {
    addLocalLog("error", `${t("actionFailed")}: ${error.message}`);
  }
}

function stopTactileSampling() {
  if (["recording", "stopping"].includes(latestCapture.state)) return;
  if (!tactileSelection.length) return;
  tactileSelection = [];
  tactileFingerprint = "";
  post("/api/tactile", { sides: [] }).catch(error => addLocalLog("error", `${t("actionFailed")}: ${error.message}`));
}

function logEntryMarkup(item, detailed = false) {
  const level = escapeHtml(item.level || "info");
  const message = escapeHtml(item.message || "");
  const time = escapeHtml(item.time || "--:--:--");
  return detailed
    ? `<div class="log-entry detailed ${level}"><time>${time}</time><span class="log-level">${level}</span><span class="log-message">${message}</span></div>`
    : `<div class="log-entry ${level}"><span class="log-level">${level}</span><span class="log-message">${message}</span></div>`;
}

function renderLogs(messages = []) {
  latestMessages = messages;
  const visible = messages.slice(hiddenLogCount);
  const fingerprint = `${language}\n${visible.map(item => `${item.time || ""}:${item.level}:${item.message}`).join("\n")}`;
  if (fingerprint === logFingerprint) return;
  logFingerprint = fingerprint;
  const list = $('#log-list');
  const preview = $('#log-preview-list');
  $('#log-count').textContent = visible.length;
  if (!visible.length) {
    list.innerHTML = `<div class="log-empty">${t("noEvents")}</div>`;
    preview.innerHTML = `<div class="log-empty">${t("noEvents")}</div>`;
    return;
  }
  list.innerHTML = visible.map(item => logEntryMarkup(item, true)).join("");
  preview.innerHTML = visible.slice(-4).map(item => logEntryMarkup(item)).join("");
  list.scrollTop = list.scrollHeight;
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

function addLocalLog(level, message) {
  const time = new Intl.DateTimeFormat(language === "zh" ? "zh-CN" : "en-GB", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
  }).format(new Date());
  logFingerprint = "";
  renderLogs([...latestMessages, { level, message, time }]);
}

function showCalibrationDialog(stage, detail = "") {
  const dialog = $('#confirm-dialog');
  const icon = $('.dialog-icon', dialog);
  const cancelButton = $('#dialog-cancel');
  const confirmButton = $('#dialog-confirm');
  const actions = $('#dialog-actions');
  const running = stage === "queued" || stage === "running";
  const terminal = stage === "completed" || stage === "failed";
  calibrationDialogStage = stage;
  calibrationDialogDetail = detail || "";
  dialog.dataset.flow = "calibration";
  icon.className = `dialog-icon${running ? " running" : stage === "completed" ? " success" : stage === "failed" ? " danger" : ""}`;
  icon.textContent = running ? "" : stage === "completed" ? "✓" : stage === "failed" ? "×" : "!";
  $('#dialog-title').textContent = t(
    running ? "calibrationRunningTitle" : stage === "completed" ? "calibrationCompletedTitle" : stage === "failed" ? "calibrationFailedTitle" : "calibrateForceTitle"
  );
  const copyKey = running ? "calibrationRunningCopy" : stage === "completed" ? "calibrationCompletedCopy" : stage === "failed" ? "calibrationFailedCopy" : "calibrateForceCopy";
  $('#dialog-copy').textContent = `${t(copyKey)}${stage === "failed" && detail ? ` ${detail}` : ""}`;
  cancelButton.hidden = stage !== "confirm";
  confirmButton.hidden = false;
  confirmButton.disabled = running;
  confirmButton.className = stage === "confirm" ? "secondary-button" : stage === "failed" ? "danger-button" : "run-button";
  confirmButton.textContent = terminal ? t("acknowledge") : running ? t("calibrationRunningTitle") : t("confirm");
  actions.classList.toggle("single-action", stage !== "confirm");
  if (!dialog.open) dialog.showModal();
}

function renderCalibration(calibration = { state: "idle", detail: "" }) {
  if (calibration.state === "completed" && lastForceCalibrationState !== "completed") {
    resetTactileFilter("filterResetAfterForce");
  }
  lastForceCalibrationState = calibration.state || "idle";
  if (!["queued", "running", "completed", "failed"].includes(calibration.state)) return;
  showCalibrationDialog(calibration.state, calibration.detail || "");
}

async function beginCalibration() {
  showCalibrationDialog("running");
  addLocalLog("info", t("calibrationRequested"));
  try {
    await post("/api/action", { action: "calibrate_force" });
  } catch (error) {
    addLocalLog("error", `${t("actionFailed")}: ${error.message}`);
    showCalibrationDialog("failed", error.message);
  }
}

async function acknowledgeCalibration() {
  const button = $('#dialog-confirm');
  button.disabled = true;
  try {
    await post("/api/calibration/ack", {});
    calibrationDialogStage = "idle";
    calibrationDialogDetail = "";
    const dialog = $('#confirm-dialog');
    delete dialog.dataset.flow;
    dialog.close("confirm");
  } catch (error) {
    button.disabled = false;
    addLocalLog("error", `${t("actionFailed")}: ${error.message}`);
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const state = await response.json();
    latestConfig = state.config || latestConfig;
    if (!configured) {
      const savedLanguage = loadLanguagePreference();
      language = savedLanguage === "en" || savedLanguage === "zh"
        ? savedLanguage
        : state.language === "en" ? "en" : state.language === "zh" ? "zh" : navigator.language.toLowerCase().startsWith("zh") ? "zh" : "en";
      setForm({ ...state.config, ...loadSetupPreferences() });
      configured = true;
      applyLanguage();
    }
    renderPhase(state);
    tactileSelection = Array.isArray(state.tactile_selection) ? state.tactile_selection : tactileSelection;
    if (activeNav === "tactile" && state.snapshot) {
      latestSnapshot = state.snapshot;
      $('#session-time').textContent = formatDuration(state.snapshot.elapsed_seconds);
    } else {
      renderSnapshot(state.snapshot);
    }
    renderTactile(state.snapshot?.tactile || {});
    renderTactileCapture(state.tactile_capture || { state: "idle" });
    renderCalibration(state.calibration || { state: "idle", detail: "" });
    renderLogs(state.messages);
  } catch (error) {
    $('#connection-label').textContent = t("error");
    $('#connection-dot').className = "status-dot error";
  }
}

async function sendAction(action) {
  try {
    await post("/api/action", { action });
  }
  catch (error) { addLocalLog("error", `${t("actionFailed")}: ${error.message}`); }
}

function confirmAction(kind) {
  const dialog = $('#confirm-dialog');
  if (kind === "calibrate_force") {
    showCalibrationDialog("confirm");
    return;
  }
  delete dialog.dataset.flow;
  const titleKey = { run: "runTitle", disconnect: "disconnectTitle", quit: "quitTitle" }[kind];
  const copyKey = { run: "runCopy", disconnect: "disconnectCopy", quit: "quitCopy" }[kind];
  const dangerous = kind === "disconnect" || kind === "quit";
  const icon = $('.dialog-icon', dialog);
  icon.className = `dialog-icon${dangerous ? " danger" : ""}`;
  icon.textContent = "!";
  $('#dialog-title').textContent = t(titleKey);
  $('#dialog-copy').textContent = t(copyKey);
  $('#dialog-cancel').hidden = false;
  $('#dialog-confirm').hidden = false;
  $('#dialog-confirm').disabled = false;
  $('#dialog-confirm').textContent = t("confirm");
  $('#dialog-confirm').className = dangerous ? "danger-button" : kind === "run" ? "run-button" : "secondary-button";
  $('#dialog-actions').classList.remove("single-action");
  dialog.showModal();
  dialog.addEventListener("close", () => { if (dialog.returnValue === "confirm") sendAction(kind); }, { once: true });
}

function closeSidebar() { document.body.classList.remove("sidebar-open"); }

$('#setup-form').addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  if (!validateSetupForm(form)) return;
  const button = $('.primary-button', form);
  button.disabled = true;
  setupSubmitting = true;
  try { await post("/api/setup", formPayload()); }
  catch (reason) { renderSetupErrors([reason.message]); button.disabled = false; }
  finally { setupSubmitting = false; }
});
$('#setup-form').addEventListener("input", () => {
  saveSetupPreferences();
  if (setupErrors.length) clearSetupErrors();
});

$$('[name="left_enabled"], [name="right_enabled"]').forEach(input => input.addEventListener("change", updateHandFields));
$('[name="speed_mode"]').addEventListener("change", updateSpeedFields);
$('#language-button').addEventListener("click", () => {
  language = language === "zh" ? "en" : "zh";
  try { localStorage.setItem(languagePreferenceKey, language); }
  catch (_error) { /* Language still applies when storage is unavailable. */ }
  applyLanguage();
  logFingerprint = "";
  closeSidebar();
});
$('#tracking-button').addEventListener("click", event => {
  const action = event.currentTarget.dataset.action || "run";
  if (action === "run") confirmAction("run");
  else sendAction("pause");
});
$('#speed-button').addEventListener("click", () => sendAction("speed_mode"));
$('#motion-filter-button').addEventListener("click", () => sendAction("motion_filter"));
$('#force-calibration-button').addEventListener("click", () => confirmAction("calibrate_force"));
$('#dialog-confirm').addEventListener("click", event => {
  if ($('#confirm-dialog').dataset.flow !== "calibration") return;
  event.preventDefault();
  if (calibrationDialogStage === "confirm") beginCalibration();
  else if (["completed", "failed"].includes(calibrationDialogStage)) acknowledgeCalibration();
});
$('#confirm-dialog').addEventListener("cancel", event => {
  if (
    event.currentTarget.dataset.flow === "calibration"
    && calibrationDialogStage !== "confirm"
  ) event.preventDefault();
});
$('#confirm-dialog').addEventListener("close", event => {
  if (
    event.currentTarget.dataset.flow === "calibration"
    && calibrationDialogStage === "confirm"
  ) {
    calibrationDialogStage = "idle";
    calibrationDialogDetail = "";
    delete event.currentTarget.dataset.flow;
  }
});
$('#disconnect-button').addEventListener("click", () => confirmAction("disconnect"));
$('#clear-log').addEventListener("click", () => {
  hiddenLogCount += latestMessages.slice(hiddenLogCount).length;
  logFingerprint = "";
  renderLogs(latestMessages);
});
$('#view-all-logs').addEventListener("click", () => $('[data-nav="logs"]').click());
$('#menu-button').addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
$('#sidebar-backdrop').addEventListener("click", closeSidebar);
$$('.nav-item').forEach(button => button.addEventListener("click", () => {
  const previousNav = activeNav;
  if (button.dataset.nav === "preferences") {
    $('#preferences-dialog').showModal();
    closeSidebar();
    return;
  }
  activeNav = button.dataset.nav;
  if (activeNav === "tactile") {
    $('#dashboard-view').hidden = true;
    $('#logs-view').hidden = true;
    $('#tactile-view').hidden = false;
    $('#page-name').textContent = t("tactile");
    window.scrollTo({ top: 0, behavior: "smooth" });
    const enabledSides = ["left", "right"].filter(side => latestSnapshot?.[`${side}_enabled`]);
    const initialSelection = enabledSides.length === 1 ? enabledSides : (tactileSelection.length ? tactileSelection : enabledSides);
    setTactileSelection(initialSelection);
  } else {
    $('#tactile-view').hidden = true;
    $('#logs-view').hidden = activeNav !== "logs";
    $('#dashboard-view').hidden = lastPhase === "setup" || activeNav === "logs";
    $('#page-name').textContent = t(activeNav === "setup" ? "connection" : activeNav === "logs" ? "systemLog" : "dashboard");
    if (previousNav === "tactile") stopTactileSampling();
    if (activeNav === "logs") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else if (activeNav === "dashboard") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }
  $$('.nav-item').forEach(item => item.classList.toggle("active", item === button));
  closeSidebar();
}));
$$('#tactile-side-selector button').forEach(button => button.addEventListener("click", () => {
  setTactileSelection(button.dataset.tactileSides.split(","));
}));
$$('#tactile-display-selector button').forEach(button => button.addEventListener("click", () => {
  tactileDisplayMode = button.dataset.tactileDisplay;
  tactileFingerprint = "";
  renderTactileFilterPanel();
  renderTactile(latestSnapshot?.tactile || {});
}));
$$('#tactile-processing-selector button').forEach(button => button.addEventListener("click", () => {
  if (tactileFilter.status === "calibrating") return;
  const nextMode = button.dataset.tactileProcessing;
  if (nextMode === tactileProcessingMode) return;
  tactileProcessingMode = nextMode;
  tactileFilter.activeCount = null;
  tactileFilter.suppressedCount = null;
  tactileFilter.moduleStateCounts = null;
  clearTactileTemporalState();
  renderTactileFilterPanel();
  renderTactile(latestSnapshot?.tactile || {});
}));
$('#tactile-filter-sensitivity').addEventListener("change", () => {
  clearTactileTemporalState();
  renderTactile(latestSnapshot?.tactile || {});
});
$('#tactile-drift-compensation').addEventListener("change", () => {
  clearTactileTemporalState();
  renderTactile(latestSnapshot?.tactile || {});
});
$('#tactile-zero-button').addEventListener("click", beginTactileBaselineLearning);
$('#tactile-capture-form').addEventListener("input", () => {
  captureRequestError = "";
  $('#capture-error').textContent = "";
  saveCapturePreferences();
});
$('#tactile-capture-form').addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  captureRequestError = "";
  $('#capture-error').textContent = "";
  if (!tactileSelection.length) {
    $('#capture-error').textContent = t("captureSelectHand");
    return;
  }
  if (!form.reportValidity()) return;
  saveCapturePreferences();
  $('#capture-start').disabled = true;
  try {
    const result = await post("/api/tactile/capture", {
      action: "start",
      sides: tactileSelection,
      frequency_hz: Number(form.elements.capture_frequency.value),
      duration_seconds: Number(form.elements.capture_duration.value),
      output_path: form.elements.capture_output.value.trim()
    });
    captureRequestError = "";
    renderTactileCapture(result.capture);
  } catch (error) {
    captureRequestError = error.message;
    $('#capture-error').textContent = captureRequestError;
  } finally {
    $('#capture-start').disabled = false;
  }
});
$('#capture-stop').addEventListener("click", async () => {
  captureRequestError = "";
  $('#capture-error').textContent = "";
  $('#capture-stop').disabled = true;
  try {
    const result = await post("/api/tactile/capture", { action: "stop" });
    captureRequestError = "";
    renderTactileCapture(result.capture);
  } catch (error) {
    captureRequestError = error.message;
    $('#capture-error').textContent = captureRequestError;
    $('#capture-stop').disabled = false;
  }
});
$('#tactile-hands').addEventListener("pointermove", event => {
  const cell = event.target.closest(".tactile-cell");
  const tooltip = $('#tactile-tooltip');
  if (!cell) {
    activeTactileCell = null;
    tooltip.hidden = true;
    return;
  }
  activeTactileCell = cell;
  tooltip.textContent = cell.dataset.tooltip;
  tooltip.hidden = false;
  const margin = 14;
  const width = tooltip.offsetWidth;
  const height = tooltip.offsetHeight;
  tooltip.style.left = `${Math.min(event.clientX + margin, window.innerWidth - width - 8)}px`;
  tooltip.style.top = `${Math.min(event.clientY + margin, window.innerHeight - height - 8)}px`;
});
$('#tactile-hands').addEventListener("pointerleave", () => {
  activeTactileCell = null;
  $('#tactile-tooltip').hidden = true;
});
$('#preferences-close').addEventListener("click", () => $('#preferences-dialog').close());
$('#font-size-input').addEventListener("change", event => setFontSize(event.currentTarget.value));
$('#font-decrease').addEventListener("click", () => setFontSize(preferences.fontSize - 1));
$('#font-increase').addEventListener("click", () => setFontSize(preferences.fontSize + 1));
$$('.theme-swatch').forEach(button => button.addEventListener("click", () => {
  preferences.accent = button.dataset.color;
  applyPreferences();
}));
$('#custom-color-input').addEventListener("input", event => {
  preferences.accent = event.currentTarget.value;
  applyPreferences();
});
$('#preferences-reset').addEventListener("click", () => {
  preferences = { ...defaultPreferences };
  applyPreferences();
});
$('#shutdown-button').addEventListener("click", () => {
  if (lastPhase !== "setup") return;
  closeSidebar();
  confirmAction("quit");
});

loadPreferences();
loadCapturePreferences();
applyLanguage();
renderLogs([]);
async function runRefreshLoop() {
  await refresh();
  const configuredTactileRate = Math.max(1, Math.min(60, Number(latestSnapshot?.tactile?.target_hz || 10)));
  window.setTimeout(runRefreshLoop, activeNav === "tactile" ? 1000 / configuredTactileRate : 250);
}
runRefreshLoop();
