import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, test } from 'vitest'

import { CameraPanel, containPoint } from './CameraPanel'

describe('containPoint', () => {
  test('accounts for letterboxing around a 16:9 camera image', () => {
    expect(containPoint(0, 0, 1000, 1000)).toEqual([0, 218.75])
    expect(containPoint(1, 1, 1000, 1000)).toEqual([1000, 781.25])
  })
})

test('switches between RGB overlay and keypoints-only views', () => {
  render(<CameraPanel landmarks={null} />)

  const image = screen.getByAltText('D435 RGB stream')
  expect(image).not.toHaveClass('camera-source-hidden')
  fireEvent.click(screen.getByRole('button', { name: 'Keypoints Only' }))
  expect(image).toHaveClass('camera-source-hidden')
  fireEvent.click(screen.getByRole('button', { name: 'RGB + Tracking' }))
  expect(image).not.toHaveClass('camera-source-hidden')
})

test('shows independent left and right hand detections', () => {
  const landmarks = Array.from({ length: 21 }, () => [0.5, 0.5])
  render(<CameraPanel landmarks={landmarks} detectedHands={[
    { handedness: 'Left', confidence: 0.91, landmarks_2d: landmarks },
    { handedness: 'Right', confidence: 0.96, landmarks_2d: landmarks },
  ]} />)

  expect(screen.getByText(/Left/)).toHaveTextContent('91%')
  expect(screen.getByText(/Right/)).toHaveTextContent('96%')
})
