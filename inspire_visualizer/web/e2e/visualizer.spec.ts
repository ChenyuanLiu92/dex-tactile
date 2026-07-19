import { expect, test } from '@playwright/test'
import { PNG } from 'pngjs'

const DEVICE_WEBSOCKET = /^wss?:\/\/[^/]+\/api\/ws$/
const VISION_WEBSOCKET = /^wss?:\/\/[^/]+\/vision\/api\/ws$/

test.beforeEach(async ({ page }) => {
  await page.route('**/api/control-owner', (route) => route.fulfill({ json: {
    owner: 'vision',
    vision_state: 'DISARMED',
    manual_control_enabled: false,
  } }))
  await page.route('**/api/tactile-calibration/*', (route) => route.fulfill({ json: null }))
  await page.routeWebSocket(VISION_WEBSOCKET, () => undefined)
})

const ONLINE_HAND = {
  connection: 'online',
  actual_angles: [800, 700, 600, 500, 650, 400],
  armed: false,
  updated_at: 1,
  error: null,
  tactile: {
    profile: 'piezoresistive_v1',
    state: 'live',
    target_hz: 20,
    sample_hz: 20,
    updated_at: 1,
    error: null,
  },
} as const

test('renders both URDF hands on desktop and mobile', async ({ page }, testInfo) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.addInitScript(() => localStorage.clear())

  await page.routeWebSocket(DEVICE_WEBSOCKET, (socket) => {
    const snapshot = JSON.stringify({
      type: 'snapshot',
      hands: {
        left: { side: 'left', ...ONLINE_HAND },
        right: { side: 'right', ...ONLINE_HAND },
      },
    })
    let closed = false
    const timer = setTimeout(() => { if (!closed) socket.send(snapshot) }, 75)
    socket.onClose(() => { closed = true; clearTimeout(timer) })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Digital Twin' }).click()
  await expect(page.getByRole('button', { name: 'Left' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Right' })).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'J1 Little position' })).toHaveValue('800')

  await page.waitForFunction(() => {
    const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[]
    return resources.filter((entry) => entry.name.endsWith('.STL')).length >= 26
  })
  await page.waitForTimeout(500)

  const sceneShell = page.getByTestId('scene-shell')
  const canvas = sceneShell.locator('canvas')
  await expect(sceneShell).toHaveAttribute('data-grid-level', 'standard')
  const canvasBox = await canvas.boundingBox()
  expect(canvasBox).not.toBeNull()
  await page.mouse.move(
    (canvasBox?.x ?? 0) + (canvasBox?.width ?? 0) / 2,
    (canvasBox?.y ?? 0) + (canvasBox?.height ?? 0) / 2,
  )
  for (let step = 0; step < 12; step += 1) await page.mouse.wheel(0, -100)
  await expect(sceneShell).toHaveAttribute('data-grid-level', /fine|micro/)
  await page.getByTitle('Reset view').click()
  await expect(sceneShell).toHaveAttribute('data-grid-level', 'standard')

  await expect(page.getByText('WORLD', { exact: true })).toBeVisible()
  await expect(page.getByText('L BASE / MOUNT', { exact: true })).toBeVisible()
  await expect(page.getByText('R BASE / MOUNT', { exact: true })).toBeVisible()
  await expect(page.getByText('L J1', { exact: true })).toBeVisible()
  await expect(page.getByText('L J6', { exact: true })).toBeVisible()
  await expect(page.getByText('R J1', { exact: true })).toBeVisible()
  await expect(page.getByText('R J6', { exact: true })).toBeVisible()

  await page.getByTitle('Coordinate frames').click()
  await page.getByRole('menuitemradio', { name: 'Drive joint axes' }).click()
  await expect(page.getByText('WORLD', { exact: true })).toBeHidden()
  await expect(page.getByText('L BASE / MOUNT', { exact: true })).toBeHidden()
  await expect(page.getByText('L J1', { exact: true })).toBeVisible()

  await page.getByTitle('Coordinate frames').click()
  await page.getByRole('menuitemradio', { name: 'Off' }).click()
  await expect(page.getByText('WORLD', { exact: true })).toBeHidden()
  await expect(page.getByText('L BASE / MOUNT', { exact: true })).toBeHidden()
  await expect(page.getByText('L J1', { exact: true })).toBeHidden()

  await page.getByTitle('Toggle grid').click()
  await expect(canvas).toBeVisible()
  const canvasImage = PNG.sync.read(await canvas.screenshot())
  const quantizedColors = new Set<string>()
  const counts = new Map<string, number>()
  for (let index = 0; index < canvasImage.data.length; index += 4) {
    const key = `${canvasImage.data[index] >> 4},${canvasImage.data[index + 1] >> 4},${canvasImage.data[index + 2] >> 4}`
    quantizedColors.add(key)
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  const pixelCount = canvasImage.width * canvasImage.height
  const dominantPixels = Math.max(...counts.values())
  const background = canvasImage.data.slice(0, 3)
  const backgroundLuminance = (background[0] + background[1] + background[2]) / 3
  let changedTopPixels = 0
  for (let x = 0; x < canvasImage.width; x += 1) {
    const index = x * 4
    const distance =
      Math.abs(canvasImage.data[index] - background[0]) +
      Math.abs(canvasImage.data[index + 1] - background[1]) +
      Math.abs(canvasImage.data[index + 2] - background[2])
    if (distance > 12) changedTopPixels += 1
  }
  expect(quantizedColors.size).toBeGreaterThan(20)
  expect(dominantPixels / pixelCount).toBeLessThan(0.97)
  expect(changedTopPixels / canvasImage.width).toBeLessThan(0.01)
  expect(backgroundLuminance).toBeLessThan(35)

  await page.getByTitle('Toggle grid').click()
  await page.getByTitle('Coordinate frames').click()
  await page.getByRole('menuitemradio', { name: 'All' }).click()
  await expect(page.getByText('WORLD', { exact: true })).toBeVisible()
  await page.waitForTimeout(150)

  const viewer = page.locator('.viewer-column')
  const expandedViewerWidth = (await viewer.boundingBox())?.width ?? 0
  await page.getByTitle('Collapse control panel').click()
  await expect(page.getByTitle('Expand control panel')).toBeVisible()
  await page.waitForTimeout(220)
  const collapsedViewerWidth = (await viewer.boundingBox())?.width ?? 0
  expect(collapsedViewerWidth - expandedViewerWidth).toBeGreaterThan(250)
  await page.getByTitle('Expand control panel').click()
  await page.waitForTimeout(220)

  const separator = page.getByRole('separator', { name: 'Resize control panel' })
  const separatorBox = await separator.boundingBox()
  expect(separatorBox).not.toBeNull()
  await page.mouse.move((separatorBox?.x ?? 0) + 4, (separatorBox?.y ?? 0) + 200)
  await page.mouse.down()
  await page.mouse.move((separatorBox?.x ?? 0) - 76, (separatorBox?.y ?? 0) + 200)
  await page.mouse.up()
  await expect(separator).toHaveAttribute('aria-valuenow', '460')

  await page.screenshot({ path: testInfo.outputPath('desktop-both-hands.png'), fullPage: true })

  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 1920, height: 1080 },
  ]) {
    await page.setViewportSize(viewport)
    await page.waitForTimeout(120)
    const viewerBox = await viewer.boundingBox()
    const inspectorBox = await page.locator('.inspector-shell').boundingBox()
    expect(viewerBox).not.toBeNull()
    expect(inspectorBox).not.toBeNull()
    expect((viewerBox?.x ?? 0) + (viewerBox?.width ?? 0)).toBeLessThanOrEqual(
      (inspectorBox?.x ?? 0) + 1,
    )
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      viewport.width,
    )
  }

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole('heading', { name: 'Right hand' })).toBeVisible()
  const toolsBox = await page.getByLabel('View tools').boundingBox()
  const tabsBox = await page.getByLabel('Active hand').boundingBox()
  expect(toolsBox).not.toBeNull()
  expect(tabsBox).not.toBeNull()
  expect((toolsBox?.y ?? 0) + (toolsBox?.height ?? 0)).toBeLessThan(tabsBox?.y ?? 0)
  const lastActualBox = await page.locator('.actual-value').last().boundingBox()
  expect(lastActualBox).not.toBeNull()
  expect((lastActualBox?.x ?? 0) + (lastActualBox?.width ?? 0)).toBeLessThanOrEqual(390)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.screenshot({ path: testInfo.outputPath('mobile-both-hands.png'), fullPage: true })

  expect(pageErrors).toEqual([])
})

test('renders a complete piezoresistive frame in the 2D atlas and combined view', async ({ page }, testInfo) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  const shapes = [
    ['little_tip_end', 3, 3], ['little_tip', 12, 8], ['little_pad', 10, 8],
    ['ring_tip_end', 3, 3], ['ring_tip', 12, 8], ['ring_pad', 10, 8],
    ['middle_tip_end', 3, 3], ['middle_tip', 12, 8], ['middle_pad', 10, 8],
    ['index_tip_end', 3, 3], ['index_tip', 12, 8], ['index_pad', 10, 8],
    ['thumb_tip_end', 3, 3], ['thumb_tip', 12, 8], ['thumb_middle', 3, 3],
    ['thumb_pad', 12, 8], ['palm', 8, 14],
  ] as const

  await page.routeWebSocket(DEVICE_WEBSOCKET, (socket) => {
    let closed = false
    const snapshotTimer = setTimeout(() => { if (!closed) socket.send(JSON.stringify({
      type: 'snapshot',
      hands: {
        left: { side: 'left', ...ONLINE_HAND },
        right: {
          side: 'right', connection: 'offline', actual_angles: null, armed: false,
          updated_at: null, error: null,
          tactile: { profile: 'disabled', state: 'off', target_hz: 20, sample_hz: 0, updated_at: null, error: null },
        },
      },
    })) }, 75)
    const tactileTimer = setTimeout(() => { if (!closed) socket.send(JSON.stringify({
      type: 'tactile_frame',
      side: 'left',
      profile: 'piezoresistive_v1',
      sequence: 1,
      captured_at: 10,
      regions: shapes.map(([id, rows, columns], regionIndex) => ({
        id, rows, columns, metrics: null,
        values: Array.from({ length: rows * columns }, (_, index) =>
          (index + regionIndex * 17) % 1800,
        ),
      })),
    })) }, 140)
    socket.onClose(() => {
      closed = true
      clearTimeout(snapshotTimer)
      clearTimeout(tactileTimer)
    })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Digital Twin' }).click()
  await expect(page.getByRole('button', { name: 'Tactile', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Tactile', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Surface telemetry' })).toBeVisible()
  await expect(page.getByText('PIEZO / 1062')).toBeVisible()
  const atlas = page.getByTestId('tactile-atlas').filter({ visible: true })
  await expect(atlas).toHaveClass(/view-heatmap/)
  await expect(atlas.getByRole('button', { name: 'Palm' })).toBeVisible()
  await page.getByRole('button', { name: 'Surface', exact: true }).click()
  await expect(atlas).toHaveClass(/view-surface/)
  await page.screenshot({ path: testInfo.outputPath('desktop-left-tactile.png'), fullPage: true })

  await page.getByRole('button', { name: 'Motion + Tactile' }).click()
  await expect(page.locator('.combined-workspace')).toBeVisible()
  await expect(page.locator('.combined-workspace').getByTestId('scene-shell')).toHaveAttribute('data-workspace-mode', 'motion')
  await expect(page.locator('.combined-workspace').getByTestId('tactile-atlas')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Surface telemetry' })).toBeVisible()
  await page.waitForTimeout(200)
  await page.screenshot({ path: testInfo.outputPath('desktop-left-combined.png'), fullPage: true })

  const palmCanvas = page.locator('.combined-workspace')
    .getByTestId('tactile-atlas')
    .getByRole('button', { name: 'Palm' })
    .locator('canvas')
  const canvasImage = PNG.sync.read(await palmCanvas.screenshot())
  const surfaceColors = new Set<string>()
  for (let index = 0; index < canvasImage.data.length; index += 4) {
    const red = canvasImage.data[index]
    const green = canvasImage.data[index + 1]
    const blue = canvasImage.data[index + 2]
    surfaceColors.add(`${red >> 3},${green >> 3},${blue >> 3}`)
  }
  expect(surfaceColors.size).toBeGreaterThan(8)
  expect(pageErrors).toEqual([])
})

test('switches the complete workstation surface to Chinese while preserving engineering identifiers', async ({ page }, testInfo) => {
  await page.addInitScript(() => localStorage.clear())
  await page.route('**/api/config', async (route) => route.fulfill({
    json: {
      left: { enabled: true, host: '192.0.2.10', port: 6000, tactile_profile: 'piezoresistive_v1', tactile_target_hz: 20 },
      right: { enabled: false, host: '192.0.2.11', port: 6000, tactile_profile: 'disabled', tactile_target_hz: 20 },
    },
  }))
  await page.routeWebSocket(DEVICE_WEBSOCKET, (socket) => {
    socket.send(JSON.stringify({
      type: 'snapshot',
      hands: {
        left: { side: 'left', ...ONLINE_HAND },
        right: { side: 'right', connection: 'offline', actual_angles: null, armed: false, updated_at: null, error: null, tactile: { profile: 'disabled', state: 'off', target_hz: 20, sample_hz: 0, updated_at: null, error: null } },
      },
    }))
    let sequence = 0
    let closed = false
    const timer = setInterval(() => {
      if (closed) return
      sequence += 1
      socket.send(JSON.stringify({
        type: 'tactile_frame', side: 'left', profile: 'piezoresistive_v1', sequence, captured_at: sequence,
        regions: [{ id: 'index_tip', rows: 12, columns: 8, metrics: null, values: Array(96).fill(100) }],
      }))
      if (sequence >= 30) clearInterval(timer)
    }, 80)
    socket.onClose(() => { closed = true; clearInterval(timer) })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Digital Twin' }).click()
  await expect(page.getByRole('button', { name: '中文' })).toBeVisible()
  await page.getByRole('button', { name: '中文' }).click()

  await expect(page.getByText('灵巧机器人工作台')).toBeVisible()
  await expect(page.getByRole('button', { name: '运动', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '左手' })).toBeVisible()
  await expect(page.getByRole('button', { name: '执行姿态' })).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'J1 小指位置' })).toBeVisible()
  await expect(page.getByText('WORLD', { exact: true })).toBeVisible()

  await page.getByTitle('坐标系').click()
  await expect(page.getByRole('menuitemradio', { name: '驱动关节轴' })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByTitle('设备设置').click()
  await expect(page.getByRole('heading', { name: '设备端点' })).toBeVisible()
  await expect(page.getByText('Modbus TCP', { exact: true })).toBeVisible()
  await expect(page.getByText('IP 地址', { exact: true }).first()).toBeVisible()
  await page.getByTitle('关闭').click()

  await page.getByRole('button', { name: '触觉', exact: true }).click()
  await expect(page.getByRole('heading', { name: '表面触觉遥测' })).toBeVisible()
  await expect(page.getByText('PIEZO / 1062')).toBeVisible()
  await expect(page.getByText('接触区域')).toBeVisible()
  await expect(page.getByRole('button', { name: '食指指尖' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('desktop-chinese-ui.png'), fullPage: true })
})

test('guides tactile calibration directly on the 2D hand atlas', async ({ page }, testInfo) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  let pressed = false
  const shapes = [
    ['little_tip_end', 3, 3], ['little_tip', 12, 8], ['little_pad', 10, 8],
    ['ring_tip_end', 3, 3], ['ring_tip', 12, 8], ['ring_pad', 10, 8],
    ['middle_tip_end', 3, 3], ['middle_tip', 12, 8], ['middle_pad', 10, 8],
    ['index_tip_end', 3, 3], ['index_tip', 12, 8], ['index_pad', 10, 8],
    ['thumb_tip_end', 3, 3], ['thumb_tip', 12, 8], ['thumb_middle', 3, 3],
    ['thumb_pad', 12, 8], ['palm', 8, 14],
  ] as const

  await page.route('**/api/config', (route) => route.fulfill({ json: {
    left: { enabled: true, host: '192.0.2.10', port: 6000, tactile_profile: 'piezoresistive_v1', tactile_target_hz: 20 },
    right: { enabled: false, host: '192.0.2.11', port: 6000, tactile_profile: 'disabled', tactile_target_hz: 20 },
  } }))
  await page.route('**/api/tactile-calibration/left', async (route) => {
    if (route.request().method() === 'GET') await route.fulfill({ json: null })
    else await route.fulfill({ json: JSON.parse(route.request().postData() ?? '{}') })
  })
  await page.routeWebSocket(DEVICE_WEBSOCKET, (socket) => {
    socket.send(JSON.stringify({
      type: 'snapshot',
      hands: {
        left: { side: 'left', ...ONLINE_HAND },
        right: { side: 'right', connection: 'offline', actual_angles: null, armed: false, updated_at: null, error: null, tactile: { profile: 'disabled', state: 'off', target_hz: 20, sample_hz: 0, updated_at: null, error: null } },
      },
    }))
    let sequence = 0
    let closed = false
    const timer = setInterval(() => {
      if (closed) return
      sequence += 1
      socket.send(JSON.stringify({
        type: 'tactile_frame', side: 'left', profile: 'piezoresistive_v1', sequence, captured_at: sequence,
        regions: shapes.map(([id, rows, columns]) => ({
          id, rows, columns, metrics: null,
          values: Array.from({ length: rows * columns }, (_, index) => id === 'little_tip_end' && pressed && index === 4 ? 700 : 100),
        })),
      }))
    }, 200)
    socket.onClose(() => { closed = true; clearInterval(timer) })
  })

  await page.goto('/')
  await page.getByRole('button', { name: 'Digital Twin' }).click()
  await page.getByRole('button', { name: 'Tactile', exact: true }).click()
  await page.getByRole('button', { name: 'Calibrate map' }).click()
  const dialog = page.getByRole('dialog', { name: '2D tactile calibration' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Zero sensors' })).toBeEnabled()
  await dialog.getByRole('button', { name: 'Zero sensors' }).click()
  await expect(dialog.getByRole('heading', { name: 'Little Tip End' })).toBeVisible({ timeout: 12_000 })
  await expect(dialog.getByText('Waiting for contact')).toBeVisible()
  await dialog.getByRole('button', { name: 'Little Tip End' }).locator('canvas').waitFor({ state: 'visible' })
  await page.waitForTimeout(1_000)

  pressed = true
  await expect(dialog.getByText('Captured — release pressure')).toBeVisible({ timeout: 6_000 })
  await page.screenshot({ path: testInfo.outputPath('tactile-calibration-grounded.png'), fullPage: true })
  pressed = false
  await expect(dialog.locator('.calibration-point-strip .current')).toHaveText('2', { timeout: 2_000 })
  expect(pageErrors).toEqual([])
})
