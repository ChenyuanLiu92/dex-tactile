import { LockKeyhole, Play, UnlockKeyhole } from 'lucide-react'
import { useState } from 'react'

import { CHANNELS, type ChannelValues, type HandSide, type HandSnapshot } from '../app/types'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/messages'

export interface HandControls {
  angles: ChannelValues
  speeds: ChannelValues
  forces: ChannelValues
}

type ControlMode = 'angles' | 'speeds' | 'forces'

interface ControlPanelProps {
  side: HandSide
  hand: HandSnapshot
  controls: HandControls
  onControlsChange: (controls: HandControls) => void
  onSetArmed: (armed: boolean) => void
  onExecute: () => void
  socketConnected: boolean
  readOnly?: boolean
}

const MODE_META = {
  angles: { labelKey: 'motion.position', minimum: 0, maximum: 1000, suffix: '' },
  speeds: { labelKey: 'motion.speed', minimum: 0, maximum: 1000, suffix: '' },
  forces: { labelKey: 'motion.force', minimum: 0, maximum: 3000, suffix: ' g' },
} as const

const CHANNEL_KEYS: MessageKey[] = ['channel.little', 'channel.ring', 'channel.middle', 'channel.index', 'channel.thumbBend', 'channel.thumbRotate']

export function ControlPanel({
  side,
  hand,
  controls,
  onControlsChange,
  onSetArmed,
  onExecute,
  socketConnected,
  readOnly = false,
}: ControlPanelProps) {
  const { t } = useI18n()
  const [mode, setMode] = useState<ControlMode>('angles')
  const [linked, setLinked] = useState(true)
  const meta = MODE_META[mode]
  const values = controls[mode]
  const actual = hand.actual_angles

  const setValue = (index: number, value: number) => {
    const next = [...values] as ChannelValues
    if (mode !== 'angles' && linked) next.fill(value)
    else next[index] = value
    onControlsChange({ ...controls, [mode]: next })
  }

  return (
    <aside className="control-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t('motion.device', { side: t(side === 'left' ? 'common.left' : 'common.right') })}</span>
          <h2>{t(side === 'left' ? 'common.leftHand' : 'common.rightHand')}</h2>
        </div>
        <span className={`connection-dot ${hand.connection}`}>
          {readOnly ? 'VISION CONTROL' : t(hand.connection === 'online' ? 'common.online' : 'common.offline')}
        </span>
      </div>

      <div className="segment-control" aria-label={t('motion.parameter')}>
        {(Object.keys(MODE_META) as ControlMode[]).map((key) => (
          <button
            type="button"
            key={key}
            className={mode === key ? 'active' : ''}
            onClick={() => setMode(key)}
          >
            {t(MODE_META[key].labelKey)}
          </button>
        ))}
      </div>

      {mode !== 'angles' ? (
        <label className="linked-toggle">
          <input type="checkbox" checked={linked} onChange={(event) => setLinked(event.target.checked)} />
          {t('motion.linkAll')}
        </label>
      ) : null}

      <div className="slider-legend" aria-hidden="true">
        <span>{t('motion.axis')}</span>
        <span />
        <span>{t('motion.target')}</span>
        <span>{t(mode === 'angles' ? 'motion.actualShort' : 'motion.unit')}</span>
      </div>
      <div className="slider-list">
        {(mode !== 'angles' && linked ? CHANNELS.slice(0, 1) : CHANNELS).map((channel, index) => {
          const value = values[index]
          return (
            <label className="channel-row" key={channel.key}>
              <span className="channel-name">
                <b>{mode !== 'angles' && linked ? t('motion.all') : `J${index + 1}`}</b>
                {mode !== 'angles' && linked ? t('motion.allChannels') : t(CHANNEL_KEYS[index]!)}
              </span>
              <input
                type="range"
                disabled={readOnly}
                min={meta.minimum}
                max={meta.maximum}
                step={1}
                value={value}
                onChange={(event) => setValue(index, Number(event.target.value))}
              />
              <input
                className="number-input"
                aria-label={
                  mode !== 'angles' && linked
                    ? t('motion.inputAll', { parameter: t(meta.labelKey).toLocaleLowerCase() })
                    : t('motion.inputJoint', { joint: `J${index + 1}`, channel: t(CHANNEL_KEYS[index]!), parameter: t(meta.labelKey).toLocaleLowerCase() })
                }
                type="number"
                disabled={readOnly}
                min={meta.minimum}
                max={meta.maximum}
                value={value}
                onChange={(event) =>
                  setValue(
                    index,
                    Math.min(meta.maximum, Math.max(meta.minimum, Number(event.target.value))),
                  )
                }
              />
              {mode === 'angles' ? (
                <span className="actual-value" title={t('motion.actualPosition')}>
                  {actual?.[index] ?? '--'}
                </span>
              ) : (
                <span className="unit-label">{meta.suffix}</span>
              )}
            </label>
          )
        })}
      </div>

      <div className="safety-strip">
        <button
          type="button"
          role="switch"
          aria-checked={hand.armed}
          className={`arm-button ${hand.armed ? 'armed' : ''}`}
          disabled={readOnly || !socketConnected || hand.connection !== 'online'}
          onClick={() => onSetArmed(!hand.armed)}
        >
          {hand.armed ? <UnlockKeyhole size={17} /> : <LockKeyhole size={17} />}
          {t(hand.armed ? 'motion.armed' : 'motion.arm')}
        </button>
        <button
          type="button"
          className="execute-button"
          disabled={readOnly || !socketConnected || hand.connection !== 'online' || !hand.armed}
          onClick={onExecute}
        >
          <Play size={17} fill="currentColor" />
          {t('motion.execute')}
        </button>
      </div>
    </aside>
  )
}
