import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  PANEL_STORAGE_KEY,
  ResizableInspector,
} from '../src/device-control/ResizableInspector'

class MemoryStorage {
  private values = new Map<string, string>()

  getItem(key: string) {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string) {
    this.values.set(key, value)
  }

  clear() {
    this.values.clear()
  }
}

let storage: MemoryStorage

describe('ResizableInspector', () => {
  beforeEach(() => {
    storage = new MemoryStorage()
    Object.defineProperty(window, 'localStorage', { configurable: true, value: storage })
    Object.defineProperty(HTMLElement.prototype, 'setPointerCapture', {
      configurable: true,
      value: () => undefined,
    })
    Object.defineProperty(HTMLElement.prototype, 'releasePointerCapture', {
      configurable: true,
      value: () => undefined,
    })
  })

  afterEach(cleanup)

  it('removes inspector controls while collapsed and restores them on expand', () => {
    render(<ResizableInspector><button type="button">Inspector control</button></ResizableInspector>)

    fireEvent.click(screen.getByRole('button', { name: 'Collapse control panel' }))
    expect(screen.queryByRole('button', { name: 'Inspector control' })).not.toBeInTheDocument()
    expect(document.querySelector('.inspector-content')).toHaveAttribute('inert')

    fireEvent.click(screen.getByRole('button', { name: 'Expand control panel' }))
    expect(screen.getByRole('button', { name: 'Inspector control' })).toBeInTheDocument()
    expect(document.querySelector('.inspector-content')).not.toHaveAttribute('inert')
  })

  it('resizes with keyboard controls and clamps the width', () => {
    render(<ResizableInspector>Controls</ResizableInspector>)
    const separator = screen.getByRole('separator', { name: 'Resize control panel' })

    fireEvent.keyDown(separator, { key: 'ArrowLeft' })
    expect(separator).toHaveAttribute('aria-valuenow', '396')
    fireEvent.keyDown(separator, { key: 'End' })
    expect(separator).toHaveAttribute('aria-valuenow', '520')
    fireEvent.keyDown(separator, { key: 'ArrowLeft' })
    expect(separator).toHaveAttribute('aria-valuenow', '520')
    fireEvent.keyDown(separator, { key: 'Home' })
    expect(separator).toHaveAttribute('aria-valuenow', '320')
  })

  it('clamps pointer resizing and persists the resulting preferences', () => {
    render(<ResizableInspector>Controls</ResizableInspector>)
    const separator = screen.getByRole('separator', { name: 'Resize control panel' })

    fireEvent.pointerDown(separator, { pointerId: 3, clientX: 500 })
    fireEvent.pointerMove(separator, { pointerId: 3, clientX: 200 })
    fireEvent.pointerUp(separator, { pointerId: 3, clientX: 200 })

    expect(separator).toHaveAttribute('aria-valuenow', '520')
    expect(JSON.parse(storage.getItem(PANEL_STORAGE_KEY) ?? '{}')).toEqual({
      width: 520,
      collapsed: false,
    })
  })

  it('restores valid preferences and rejects malformed values', () => {
    storage.setItem(PANEL_STORAGE_KEY, JSON.stringify({ width: 470, collapsed: true }))
    const { unmount } = render(<ResizableInspector>Controls</ResizableInspector>)

    expect(screen.getByRole('separator', { name: 'Resize control panel' })).toHaveAttribute(
      'aria-valuenow',
      '470',
    )
    expect(screen.getByRole('button', { name: 'Expand control panel' })).toBeInTheDocument()

    unmount()
    storage.setItem(PANEL_STORAGE_KEY, JSON.stringify({ width: 'wide', collapsed: false }))
    render(<ResizableInspector>Controls</ResizableInspector>)
    expect(screen.getByRole('separator', { name: 'Resize control panel' })).toHaveAttribute(
      'aria-valuenow',
      '380',
    )
  })
})
