import { expect, test } from '@playwright/test'

test('renders guarded RH56 controls and a nonblank robot scene', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('SOFTWARE HOLD ONLY', { exact: true })).toBeVisible()
  await expect(page.getByText('DISARMED', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'ARM' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'E-STOP' })).toBeVisible()
  await expect(page.getByTestId('joint-row')).toHaveCount(12)
  await expect(page.getByTestId('actuator-row')).toHaveCount(6)
  const canvas = page.getByTestId('robot-canvas')
  await expect(canvas).toBeVisible()
  await page.waitForTimeout(2500)

  const nonblank = await canvas.evaluate((element: HTMLCanvasElement) => {
    const gl = element.getContext('webgl2') || element.getContext('webgl')
    if (!gl) return false
    const pixels = new Uint8Array(element.width * element.height * 4)
    gl.readPixels(0, 0, element.width, element.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels)
    let min = 255
    let max = 0
    for (let index = 0; index < pixels.length; index += 4) {
      min = Math.min(min, pixels[index])
      max = Math.max(max, pixels[index])
      if (max - min > 12) return true
    }
    return false
  })
  expect(nonblank).toBe(true)
  expect(errors).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('workbench.png'), fullPage: true })
})
