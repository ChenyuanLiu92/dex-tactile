import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import type { OperatorProfileSummary, ProfileApi } from '../api'
import { OperatorProfileControl } from './OperatorProfileControl'

vi.mock('../scene/RobotScene', () => ({ RobotScene: () => <div data-testid="robot-scene" /> }))
vi.mock('../camera/CameraPanel', () => ({ CameraPanel: () => <div data-testid="camera-panel" /> }))


const profiles: OperatorProfileSummary[] = [
  { id: 'default', name: 'Default', calibration_state: 'DEFAULT', active: true, updated_at: null },
  { id: 'operator-a', name: 'Operator A', calibration_state: 'UNCALIBRATED', active: false, updated_at: null },
]

function api(): ProfileApi {
  return {
    list: vi.fn().mockResolvedValue({ active_profile_id: 'default', profiles }),
    create: vi.fn().mockResolvedValue(profiles[1]),
    rename: vi.fn().mockResolvedValue(profiles[1]),
    remove: vi.fn().mockResolvedValue({ active_profile_id: 'default', profiles }),
    activate: vi.fn().mockResolvedValue(profiles[1]),
    startCalibration: vi.fn().mockResolvedValue({
      state: 'COLLECTING', profile_id: 'operator-a', pose: 'open', pose_index: 0,
      total_poses: 5, accepted_samples: 0, required_samples: 30, stability: null,
      error: null, failed_pose: null,
    }),
    retryCalibration: vi.fn(),
    cancelCalibration: vi.fn(),
    exportProfile: vi.fn(),
    importProfile: vi.fn(),
  }
}

test('selects profiles manually and disables changes outside DISARMED', async () => {
  const profileApi = api()
  const { rerender } = render(
    <OperatorProfileControl
      current={profiles[0]}
      calibration={null}
      controlState="DISARMED"
      trackingStatus="TRACKING"
      detectedHands={[]}
      landmarks={null}
      api={profileApi}
    />,
  )

  await screen.findByRole('option', { name: 'Operator A' })
  fireEvent.change(screen.getByLabelText('Operator profile'), { target: { value: 'operator-a' } })
  await waitFor(() => expect(profileApi.activate).toHaveBeenCalledWith('operator-a'))

  rerender(
    <OperatorProfileControl
      current={profiles[0]}
      calibration={null}
      controlState="ARMED"
      trackingStatus="TRACKING"
      detectedHands={[]}
      landmarks={null}
      api={profileApi}
    />,
  )
  expect(screen.getByLabelText('Operator profile')).toBeDisabled()
})


test('creates a profile and starts guided calibration from the manager', async () => {
  const profileApi = api()
  render(
    <OperatorProfileControl
      current={profiles[0]}
      calibration={null}
      controlState="DISARMED"
      trackingStatus="TRACKING"
      detectedHands={[]}
      landmarks={null}
      api={profileApi}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Manage operator profiles' }))
  fireEvent.change(screen.getByLabelText('Profile name'), { target: { value: 'Operator A' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create profile' }))
  await waitFor(() => expect(profileApi.create).toHaveBeenCalledWith('Operator A'))

  fireEvent.click(screen.getByRole('button', { name: 'Calibrate Operator A' }))
  await waitFor(() => expect(profileApi.startCalibration).toHaveBeenCalledWith('operator-a'))
})


test('renames an operator profile in the manager', async () => {
  const profileApi = api()
  render(
    <OperatorProfileControl
      current={profiles[0]}
      calibration={null}
      controlState="DISARMED"
      trackingStatus="TRACKING"
      detectedHands={[]}
      landmarks={null}
      api={profileApi}
    />,
  )

  fireEvent.click(screen.getByRole('button', { name: 'Manage operator profiles' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Rename profile' }))
  fireEvent.change(screen.getByLabelText('Rename profile'), { target: { value: 'Operator B' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save profile name' }))

  await waitFor(() => expect(profileApi.rename).toHaveBeenCalledWith('operator-a', 'Operator B'))
})


test('shows the automatic five-pose calibration workspace', async () => {
  const profileApi = api()
  render(
    <OperatorProfileControl
      current={{ ...profiles[1], active: true }}
      calibration={{
        state: 'COLLECTING', profile_id: 'operator-a', pose: 'open', pose_index: 0,
        total_poses: 5, accepted_samples: 12, required_samples: 30, stability: 0.01,
        error: null, failed_pose: null,
      }}
      controlState="DISARMED"
      trackingStatus="TRACKING"
      detectedHands={[]}
      landmarks={null}
      api={profileApi}
    />,
  )

  expect(screen.getByRole('dialog', { name: 'Operator calibration' })).toHaveTextContent('OPEN HAND')
  expect(screen.getByText('12 / 30')).toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Cancel calibration' })[0])
  await waitFor(() => expect(profileApi.cancelCalibration).toHaveBeenCalledWith('operator-a'))
})
