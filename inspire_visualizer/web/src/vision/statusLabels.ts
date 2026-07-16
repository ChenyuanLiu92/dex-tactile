import type { MessageKey } from '../i18n/messages'
import type { ControlState, TrackingStatus } from './api'

export const TRACKING_STATUS_KEYS: Record<TrackingStatus, MessageKey> = {
  STARTING: 'status.starting',
  SEARCHING: 'status.searching',
  WRONG_HAND: 'status.wrongHand',
  TRACKING: 'status.tracking',
  LOST: 'status.lost',
  CAMERA_ERROR: 'status.cameraError',
}

export const CONTROL_STATE_KEYS: Record<ControlState, MessageKey> = {
  DISCONNECTED: 'control.disconnected',
  DISARMED: 'control.disarmed',
  ARMING: 'control.arming',
  ARMED: 'control.armed',
  POSITIONING: 'control.positioning',
  HOLDING: 'control.holding',
  ESTOPPED: 'control.estopped',
  FAULT: 'control.fault',
}
