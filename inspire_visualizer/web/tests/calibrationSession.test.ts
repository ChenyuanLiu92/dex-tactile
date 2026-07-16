import { describe, expect, it } from 'vitest'
import { contactStep, initialCalibrationSession, type GuidedCalibrationSession } from '../src/tactile/calibrationSession'

const observation = { row: 2, column: 3, peak: 100, active: 4, totalWeight: 300 }

describe('guided calibration session', () => {
  it('tracks whether calibration is full-hand or a single-region repair', () => {
    expect(initialCalibrationSession('left').mode).toBe('full')
    expect(initialCalibrationSession('left', 'index_tip', 'single')).toMatchObject({ mode: 'single', regionId: 'index_tip' })
  })

  it('captures after six stable frames and waits for release', () => {
    let session = initialCalibrationSession('left', 'index_tip')
    for (let index = 0; index < 6; index += 1) session = contactStep(session, observation, index * 50)
    expect(session.stage).toBe('waiting_release')
    expect(session.pendingSample).toMatchObject({ observedRow: 2, observedColumn: 3 })
  })

  it('advances only after 300ms without contact', () => {
    let session: GuidedCalibrationSession = { ...initialCalibrationSession('left', 'index_tip'), stage: 'waiting_release', releaseStartedAt: 100, pendingSample: { observedRow: 2, observedColumn: 3, peak: 100, active: 4, stableMs: 250 } }
    session = contactStep(session, null, 350)
    expect(session.pointIndex).toBe(0)
    session = contactStep(session, null, 401)
    expect(session.pointIndex).toBe(1)
    expect(session.stage).toBe('waiting_contact')
  })
})
