import { PanelRightClose, PanelRightOpen } from 'lucide-react'
import {
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from 'react'
import { useI18n } from '../i18n/I18nProvider'

export const PANEL_MIN_WIDTH = 320
export const PANEL_MAX_WIDTH = 520
export const PANEL_DEFAULT_WIDTH = 380
export const PANEL_COLLAPSED_WIDTH = 48
export const PANEL_STORAGE_KEY = 'inspire.visualizer.panel.v1'

export interface PanelPreferences {
  width: number
  collapsed: boolean
}

function clampWidth(width: number): number {
  return Math.min(PANEL_MAX_WIDTH, Math.max(PANEL_MIN_WIDTH, width))
}

function loadPreferences(): PanelPreferences {
  const fallback = { width: PANEL_DEFAULT_WIDTH, collapsed: false }
  try {
    if (typeof window.localStorage?.getItem !== 'function') return fallback
    const saved = window.localStorage.getItem(PANEL_STORAGE_KEY)
    if (!saved) return fallback
    const parsed = JSON.parse(saved) as Partial<PanelPreferences>
    if (typeof parsed.width !== 'number' || typeof parsed.collapsed !== 'boolean') return fallback
    return { width: clampWidth(parsed.width), collapsed: parsed.collapsed }
  } catch {
    return fallback
  }
}

function savePreferences(preferences: PanelPreferences): void {
  try {
    if (typeof window.localStorage?.setItem === 'function') {
      window.localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(preferences))
    }
  } catch {
    // Private browsing and locked-down environments may deny local storage.
  }
}

interface ResizableInspectorProps {
  children: ReactNode
}

export function ResizableInspector({ children }: ResizableInspectorProps) {
  const { t } = useI18n()
  const [preferences, setPreferences] = useState(loadPreferences)
  const [compactLayout, setCompactLayout] = useState(
    () => typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 899px)').matches,
  )
  const [isResizing, setIsResizing] = useState(false)
  const drag = useRef<{ pointerId: number; startX: number; startWidth: number } | null>(null)
  const collapsed = preferences.collapsed && !compactLayout
  const renderedWidth = collapsed ? PANEL_COLLAPSED_WIDTH : preferences.width

  useEffect(() => savePreferences(preferences), [preferences])
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const query = window.matchMedia('(max-width: 899px)')
    const update = () => setCompactLayout(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  const setWidth = (width: number) => {
    setPreferences((current) => ({ ...current, width: clampWidth(width) }))
  }

  const toggleCollapsed = () => {
    setPreferences((current) => ({ ...current, collapsed: !current.collapsed }))
  }

  const startResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (collapsed) return
    drag.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startWidth: preferences.width,
    }
    setIsResizing(true)
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const resize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current || drag.current.pointerId !== event.pointerId) return
    setWidth(drag.current.startWidth + drag.current.startX - event.clientX)
  }

  const stopResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (drag.current?.pointerId !== event.pointerId) return
    drag.current = null
    setIsResizing(false)
    event.currentTarget.releasePointerCapture(event.pointerId)
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    let width: number | null = null
    if (event.key === 'ArrowLeft') width = preferences.width + 16
    if (event.key === 'ArrowRight') width = preferences.width - 16
    if (event.key === 'Home') width = PANEL_MIN_WIDTH
    if (event.key === 'End') width = PANEL_MAX_WIDTH
    if (width === null) return
    event.preventDefault()
    setWidth(width)
  }

  return (
    <div
      className={`inspector-shell ${collapsed ? 'collapsed' : ''} ${isResizing ? 'resizing' : ''}`}
      style={{ '--inspector-width': `${renderedWidth}px` } as CSSProperties}
    >
      <div
        className="resize-rail"
        role="separator"
        aria-label={t('inspector.resize')}
        aria-orientation="vertical"
        aria-valuemin={PANEL_MIN_WIDTH}
        aria-valuemax={PANEL_MAX_WIDTH}
        aria-valuenow={preferences.width}
        aria-disabled={collapsed}
        tabIndex={collapsed ? -1 : 0}
        onDoubleClick={toggleCollapsed}
        onKeyDown={onKeyDown}
        onPointerDown={startResize}
        onPointerMove={resize}
        onPointerUp={stopResize}
        onPointerCancel={stopResize}
      />
      <button
        type="button"
        className="panel-toggle"
        title={t(collapsed ? 'inspector.expand' : 'inspector.collapse')}
        aria-label={t(collapsed ? 'inspector.expand' : 'inspector.collapse')}
        onClick={toggleCollapsed}
      >
        {collapsed ? <PanelRightOpen size={17} /> : <PanelRightClose size={17} />}
      </button>
      <span className="collapsed-label" aria-hidden="true">{t('inspector.control')}</span>
      <div
        className="inspector-content"
        aria-hidden={collapsed}
        inert={collapsed ? true : undefined}
      >
        {children}
      </div>
    </div>
  )
}
