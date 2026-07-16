import { useCallback, useEffect, useRef, useState } from 'react'

import type { ChannelValues, HandSide, HandsSnapshot, TactileFrames } from '../app/types'
import {
  disconnectedHands,
  initialHands,
  initialTactileFrames,
  reduceServerMessage,
  reduceTactileFrame,
  type ServerMessage,
} from './socketState'

export type ClientMessage =
  | { type: 'set_armed'; side: HandSide; armed: boolean }
  | {
      type: 'execute_pose'
      side: HandSide
      command_id: string
      angles: ChannelValues
      speeds: ChannelValues
      forces: ChannelValues
    }

export type SocketStatus = 'connecting' | 'connected' | 'disconnected'

export function useDeviceSocket() {
  const [hands, setHands] = useState<HandsSnapshot>(initialHands)
  const [status, setStatus] = useState<SocketStatus>('connecting')
  const [tactileFrames, setTactileFrames] = useState<TactileFrames>(initialTactileFrames)
  const [lastError, setLastError] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let disposed = false
    let retryTimer: number | undefined

    const connect = () => {
      if (disposed) return
      setStatus('connecting')
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(`${protocol}//${window.location.host}/api/ws`)
      socketRef.current = socket
      socket.onopen = () => {
        setStatus('connected')
        setLastError(null)
      }
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as ServerMessage
        if (message.type === 'error') {
          setLastError(message.message)
          return
        }
        if (message.type === 'tactile_frame') {
          setTactileFrames((current) => reduceTactileFrame(current, message))
          return
        }
        setHands((current) => reduceServerMessage(current, message))
      }
      socket.onerror = () => setLastError('Unable to connect to the device gateway')
      socket.onclose = () => {
        if (socketRef.current === socket) socketRef.current = null
        setStatus('disconnected')
        setHands(disconnectedHands())
        setTactileFrames(initialTactileFrames)
        if (!disposed) retryTimer = window.setTimeout(connect, 1500)
      }
    }

    connect()
    return () => {
      disposed = true
      if (retryTimer !== undefined) window.clearTimeout(retryTimer)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [])

  const send = useCallback((message: ClientMessage): boolean => {
    if (socketRef.current?.readyState !== WebSocket.OPEN) {
      setLastError('The device gateway is not connected')
      return false
    }
    socketRef.current.send(JSON.stringify(message))
    return true
  }, [])

  const clearError = useCallback(() => setLastError(null), [])

  return { hands, tactileFrames, status, lastError, clearError, send }
}
