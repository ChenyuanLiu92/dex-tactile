import { useEffect, useState } from 'react'

export type TrackingStatus =
  | 'STARTING'
  | 'SEARCHING'
  | 'WRONG_HAND'
  | 'TRACKING'
  | 'LOST'
  | 'CAMERA_ERROR'

export type ControlState =
  | 'DISCONNECTED'
  | 'DISARMED'
  | 'ARMING'
  | 'ARMED'
  | 'POSITIONING'
  | 'HOLDING'
  | 'ESTOPPED'
  | 'FAULT'

export interface ControlSnapshot {
  state: ControlState
  connected: boolean
  host: string
  port: number
  actual: number[] | null
  targets: number[] | null
  commanded: number[] | null
  speeds: number[] | null
  last_write_at: number | null
  error: string | null
  preset: 'HOME' | 'OPEN' | null
  tracking_hold: boolean
  tracking_loss_ms: number | null
  modbus_output: boolean
  software_hold_only: boolean
}

export interface ContactSnapshot {
  state: 'NONE' | 'LOCKED'
  finger: 'index' | 'middle' | 'ring' | 'pinky' | null
  human_distance_mm: number | null
  projected_distance_mm: number
}

export interface DetectedHandSnapshot {
  handedness: 'Left' | 'Right'
  confidence: number
  landmarks_2d: number[][]
}

export interface OperatorProfileSummary {
  id: string
  name: string
  calibration_state: 'DEFAULT' | 'UNCALIBRATED' | 'CALIBRATED'
  active: boolean
  updated_at: string | null
}

export interface ProfileListResponse {
  active_profile_id: string
  profiles: OperatorProfileSummary[]
}

export type CalibrationPose = 'open' | 'relaxed' | 'fist' | 'thumb_opposition' | 'ok'

export interface ProfileCalibrationStatus {
  state: 'COLLECTING' | 'FAILED' | 'COMPLETE' | 'CANCELED'
  profile_id: string
  pose: CalibrationPose | null
  pose_index: number
  total_poses: number
  accepted_samples: number
  required_samples: number
  stability: number | null
  error: string | null
  failed_pose: CalibrationPose | null
}

export interface TrackingSnapshot {
  type: 'tracking'
  status: TrackingStatus
  sequence: number
  captured_at: number
  published_at: number
  capture_fps: number
  tracking_fps: number
  latency_ms: number
  handedness: string | null
  confidence: number | null
  landmarks_2d: number[][] | null
  landmarks_3d: number[][] | null
  detected_hands: DetectedHandSnapshot[]
  joints: Record<string, number> | null
  actuators: number[] | null
  contact: ContactSnapshot | null
  error: string | null
  dry_run: boolean
  modbus_output: boolean
  control: ControlSnapshot
  operator_profile: OperatorProfileSummary
  retargeting_calibration: ProfileCalibrationStatus | null
}

export const EMPTY_CONTROL: ControlSnapshot = {
  state: 'DISCONNECTED',
  connected: false,
  host: '192.0.2.10',
  port: 6000,
  actual: null,
  targets: null,
  commanded: null,
  speeds: null,
  last_write_at: null,
  error: null,
  preset: null,
  tracking_hold: false,
  tracking_loss_ms: null,
  modbus_output: false,
  software_hold_only: true,
}

export const EMPTY_SNAPSHOT: TrackingSnapshot = {
  type: 'tracking',
  status: 'STARTING',
  sequence: 0,
  captured_at: 0,
  published_at: 0,
  capture_fps: 0,
  tracking_fps: 0,
  latency_ms: 0,
  handedness: null,
  confidence: null,
  landmarks_2d: null,
  landmarks_3d: null,
  detected_hands: [],
  joints: null,
  actuators: null,
  contact: null,
  error: null,
  dry_run: true,
  modbus_output: false,
  control: EMPTY_CONTROL,
  operator_profile: {
    id: 'default', name: 'Default', calibration_state: 'DEFAULT', active: true, updated_at: null,
  },
  retargeting_calibration: null,
}

const TRACKING_STATUSES = new Set<TrackingStatus>([
  'STARTING', 'SEARCHING', 'WRONG_HAND', 'TRACKING', 'LOST', 'CAMERA_ERROR',
])
const CONTROL_STATES = new Set<ControlState>([
  'DISCONNECTED', 'DISARMED', 'ARMING', 'ARMED', 'POSITIONING', 'HOLDING',
  'ESTOPPED', 'FAULT',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function normalizeTrackingSnapshot(
  payload: unknown,
  previous: TrackingSnapshot = EMPTY_SNAPSHOT,
): TrackingSnapshot | null {
  if (!isRecord(payload) || payload.type !== 'tracking') return null

  const candidate = payload as Partial<TrackingSnapshot>
  const control: Record<string, unknown> = isRecord(candidate.control) ? candidate.control : {}
  const profile: Record<string, unknown> = isRecord(candidate.operator_profile)
    ? candidate.operator_profile
    : {}
  const status = TRACKING_STATUSES.has(candidate.status as TrackingStatus)
    ? candidate.status as TrackingStatus
    : previous.status
  const controlState = CONTROL_STATES.has(control['state'] as ControlState)
    ? control['state'] as ControlState
    : previous.control.state

  return {
    ...previous,
    ...candidate,
    type: 'tracking',
    status,
    detected_hands: Array.isArray(candidate.detected_hands)
      ? candidate.detected_hands
      : previous.detected_hands,
    control: {
      ...previous.control,
      ...control,
      state: controlState,
    } as ControlSnapshot,
    operator_profile: {
      ...previous.operator_profile,
      ...profile,
    } as OperatorProfileSummary,
  }
}

export type ControlAction = 'arm' | 'disarm' | 'estop' | 'reset' | 'reconnect'

export async function requestControl(action: ControlAction): Promise<ControlSnapshot> {
  const response = await fetch(`/vision/api/control/${action}`, {
    method: 'POST',
    headers: { 'X-RH56-Control': 'operator-confirmed' },
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.detail || `Control request failed (${response.status})`)
  return payload as ControlSnapshot
}

async function profileRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/vision/api/retargeting/profiles${path}`, init)
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.detail || `Profile request failed (${response.status})`)
  return payload as T
}

const confirmedJson = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: {
    'X-RH56-Control': 'operator-confirmed',
    ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
  },
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
})

export interface ProfileApi {
  list: () => Promise<ProfileListResponse>
  create: (name: string) => Promise<OperatorProfileSummary>
  rename: (id: string, name: string) => Promise<OperatorProfileSummary>
  remove: (id: string) => Promise<ProfileListResponse>
  activate: (id: string) => Promise<OperatorProfileSummary>
  startCalibration: (id: string) => Promise<ProfileCalibrationStatus>
  retryCalibration: (id: string) => Promise<ProfileCalibrationStatus>
  cancelCalibration: (id: string) => Promise<ProfileCalibrationStatus>
  exportProfile: (id: string) => Promise<Record<string, unknown>>
  importProfile: (document: Record<string, unknown>) => Promise<OperatorProfileSummary>
}

export const operatorProfileApi: ProfileApi = {
  list: () => profileRequest<ProfileListResponse>(''),
  create: (name) => profileRequest('', confirmedJson('POST', { name })),
  rename: (id, name) => profileRequest(`/${id}`, confirmedJson('PATCH', { name })),
  remove: (id) => profileRequest(`/${id}`, confirmedJson('DELETE')),
  activate: (id) => profileRequest(`/${id}/activate`, confirmedJson('PUT')),
  startCalibration: (id) => profileRequest(`/${id}/calibration/start`, confirmedJson('POST')),
  retryCalibration: (id) => profileRequest(`/${id}/calibration/retry`, confirmedJson('POST')),
  cancelCalibration: (id) => profileRequest(`/${id}/calibration/cancel`, confirmedJson('POST')),
  exportProfile: (id) => profileRequest(`/${id}/export`),
  importProfile: (document) => profileRequest('/import', confirmedJson('POST', document)),
}

function websocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/vision/api/ws`
}

export function useTrackingSnapshot(enabled = true, initial = EMPTY_SNAPSHOT) {
  const [snapshot, setSnapshot] = useState(initial)

  useEffect(() => {
    if (!enabled) return
    let socket: WebSocket | null = null
    let retry: number | undefined
    let active = true

    const connect = () => {
      socket = new WebSocket(websocketUrl())
      socket.onmessage = (event) => {
        try {
          setSnapshot((current) => (
            normalizeTrackingSnapshot(JSON.parse(event.data), current) ?? current
          ))
        } catch {
          // Ignore malformed telemetry and retain the last coherent snapshot.
        }
      }
      socket.onclose = () => {
        if (active) retry = window.setTimeout(connect, 1000)
      }
    }
    connect()
    return () => {
      active = false
      if (retry !== undefined) window.clearTimeout(retry)
      socket?.close()
    }
  }, [enabled])

  return snapshot
}
