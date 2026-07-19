import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { I18nProvider, useI18n } from '../src/i18n/I18nProvider'
import { CalibrationWorkspace } from '../src/tactile/CalibrationWorkspace'

function ChineseCalibration() {
  const { toggleLocale } = useI18n()
  return <>
    <button onClick={toggleLocale}>switch</button>
    <CalibrationWorkspace
      side="left"
      frame={null}
      baseline={undefined}
      threshold={1}
      scale={1}
      regionId="index_tip"
      pointIndex={0}
      stage="preflight"
      progress={0}
      regionIndex={9}
      zeroing={false}
      focusToken={0}
      wrongRegionId={null}
      onZero={() => undefined}
      onClose={() => undefined}
      onRetry={() => undefined}
      onSkip={() => undefined}
      onRefocus={() => undefined}
      onRegionSelect={() => undefined}
      onApply={() => undefined}
    />
  </>
}

describe('localized control surfaces', () => {
  it('translates the active tactile calibration preflight', () => {
    render(<I18nProvider><ChineseCalibration /></I18nProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'switch' }))
    expect(screen.getByRole('dialog', { name: '二维触觉标定' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '二维触觉标定' })).toBeInTheDocument()
    expect(screen.getByText('标定前请保持灵巧手无接触并执行归零。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '传感器归零' })).toBeDisabled()
    expect(screen.getByTitle('退出校准')).toBeInTheDocument()
  })
})
