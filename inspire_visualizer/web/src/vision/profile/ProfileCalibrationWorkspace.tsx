import { RotateCcw, X } from 'lucide-react'
import type { CSSProperties } from 'react'

import { useI18n, type MessageKey } from '../../i18n/I18nProvider'
import type { DetectedHandSnapshot, ProfileCalibrationStatus } from '../api'
import { CameraPanel } from '../camera/CameraPanel'
import { RobotScene } from '../scene/RobotScene'


const TARGET_JOINTS: Record<string, Record<string, number>> = {
  open: {},
  relaxed: {
    pinky_proximal_joint: 0.2, ring_proximal_joint: 0.2,
    middle_proximal_joint: 0.2, index_proximal_joint: 0.2,
    thumb_proximal_pitch_joint: 0.12,
  },
  fist: {
    pinky_proximal_joint: 0.85, ring_proximal_joint: 0.85,
    middle_proximal_joint: 0.85, index_proximal_joint: 0.85,
    thumb_proximal_pitch_joint: 0.7,
  },
  thumb_opposition: { thumb_proximal_yaw_joint: 0.85 },
  ok: {
    index_proximal_joint: 0.65, thumb_proximal_pitch_joint: 0.45,
    thumb_proximal_yaw_joint: 0.8,
  },
}

export function ProfileCalibrationWorkspace({
  status,
  landmarks,
  detectedHands,
  onRetry,
  onCancel,
}: {
  status: ProfileCalibrationStatus
  landmarks: number[][] | null
  detectedHands: DetectedHandSnapshot[]
  onRetry: () => void
  onCancel: () => void
}) {
  const { t } = useI18n()
  const pose = status.pose ?? status.failed_pose ?? 'open'
  const stable = status.stability != null && status.stability <= 0.02
  const progress = Math.min(1, status.accepted_samples / Math.max(status.required_samples, 1))

  return (
    <div className="profile-calibration-backdrop">
      <section className="profile-calibration-workspace" role="dialog" aria-modal="true" aria-label={t('profile.calibrationTitle')}>
        <header>
          <div><span>{t('profile.autoCapture')}</span><strong>{t('profile.calibrationTitle')}</strong></div>
          <button type="button" aria-label={t('profile.cancelCalibration')} onClick={onCancel}><X size={18} /></button>
        </header>
        <div className="profile-calibration-grid">
          <section className="profile-camera-stage">
            <CameraPanel landmarks={landmarks} detectedHands={detectedHands} />
            <div className="profile-pose-callout">
              <span>{t('profile.step', { current: Math.min(status.pose_index + 1, status.total_poses), total: status.total_poses })}</span>
              <h2>{t(`profile.pose.${pose}` as MessageKey)}</h2>
              <p>{t(`profile.hint.${pose}` as MessageKey)}</p>
            </div>
          </section>
          <section className="profile-target-stage">
            <RobotScene joints={TARGET_JOINTS[pose] ?? {}} />
            <div className="profile-target-label">URDF / TARGET POSE</div>
          </section>
          <aside className="profile-calibration-rail">
            <div className={`profile-capture-ring ${stable ? 'stable' : ''}`} style={{ '--capture-progress': `${progress * 360}deg` } as CSSProperties}>
              <div><strong>{Math.round(progress * 100)}%</strong><span>{t(stable ? 'profile.holdStill' : 'profile.findPose')}</span></div>
            </div>
            <dl>
              <div><dt>{t('profile.samples', { accepted: status.accepted_samples, required: status.required_samples })}</dt><dd>{status.stability == null ? '---' : status.stability.toFixed(3)}</dd></div>
              <div><dt>TRACKING</dt><dd>{detectedHands.some((hand) => hand.handedness === 'Right') ? 'RIGHT' : 'WAIT'}</dd></div>
            </dl>
            {status.state === 'FAILED' && <div className="profile-calibration-error"><strong>{t('profile.failed')}</strong><span>{status.error}</span></div>}
            {status.state === 'COMPLETE' && <div className="profile-calibration-complete">{t('profile.complete')}</div>}
            <footer>
              {status.state === 'FAILED' && <button type="button" onClick={onRetry}><RotateCcw size={15} />{t('profile.retryPose')}</button>}
              <button type="button" onClick={onCancel}>{t('profile.cancelCalibration')}</button>
            </footer>
          </aside>
        </div>
      </section>
    </div>
  )
}
