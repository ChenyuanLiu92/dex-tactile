import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { I18nProvider, useI18n } from '../src/i18n/I18nProvider'
import { CalibrationDialog } from '../src/tactile/CalibrationDialog'

function ChineseCalibration() {
  const { toggleLocale } = useI18n()
  return <><button onClick={toggleLocale}>switch</button><CalibrationDialog side="left" regionId="index_tip" pointIndex={0} onClose={() => undefined} onRecord={() => undefined} /></>
}

describe('localized control surfaces', () => {
  it('translates calibration instructions, regions, tooltips, and actions', () => {
    render(<I18nProvider><ChineseCalibration /></I18nProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'switch' }))
    expect(screen.getByRole('heading', { name: '触觉表面校准' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '食指指尖' })).toBeInTheDocument()
    expect(screen.getByText('请对高亮表面点进行轻柔、稳定的按压。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '记录当前点' })).toBeInTheDocument()
    expect(screen.getByTitle('左上')).toBeInTheDocument()
    expect(screen.getByText(/RH56DFTP 触觉区域/)).toBeInTheDocument()
  })
})
