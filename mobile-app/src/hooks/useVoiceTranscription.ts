import { useState, useRef, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:3002/ws/sync'
const SAMPLE_RATE = 16000
const CHUNK_SIZE = 1024

type TranscriptionStatus = 'disconnected' | 'connecting' | 'recording' | 'error'

interface UseVoiceTranscriptionReturn {
  status: TranscriptionStatus
  error: string | null
  startRecording: (onTextUpdate: (text: string, isFinal: boolean) => void) => Promise<void>
  stopRecording: () => void
}

export function useVoiceTranscription(): UseVoiceTranscriptionReturn {
  const [status, setStatus] = useState<TranscriptionStatus>('disconnected')
  const [error, setError] = useState<string | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null)
  const onTextUpdateRef = useRef<((text: string, isFinal: boolean) => void) | null>(null)

  const cleanupAudio = useCallback(() => {
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect()
      scriptProcessorRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ finish: true }))
    }
    cleanupAudio()
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('disconnected')
  }, [cleanupAudio])

  const startRecording = useCallback(
    async (onTextUpdate: (text: string, isFinal: boolean) => void) => {
      onTextUpdateRef.current = onTextUpdate
      setError(null)
      setStatus('connecting')

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: SAMPLE_RATE,
            channelCount: 1,
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        })
        streamRef.current = stream

        const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE })
        audioContextRef.current = audioContext

        const source = audioContext.createMediaStreamSource(stream)
        const scriptProcessor = audioContext.createScriptProcessor(CHUNK_SIZE, 1, 1)
        scriptProcessorRef.current = scriptProcessor

        const sendAudioChunk = (inputData: Float32Array) => {
          if (wsRef.current?.readyState !== WebSocket.OPEN) return
          const bytes = inputData.buffer
          let binary = ''
          const bytesArray = new Uint8Array(bytes)
          for (let i = 0; i < bytesArray.length; i++) {
            binary += String.fromCharCode(bytesArray[i])
          }
          const base64 = btoa(binary)
          wsRef.current.send(JSON.stringify({ bytes: base64 }))
        }

        scriptProcessor.onaudioprocess = (e) => {
          const inputData = e.inputBuffer.getChannelData(0)
          sendAudioChunk(inputData)
        }

        source.connect(scriptProcessor)
        scriptProcessor.connect(audioContext.destination)

        const ws = new WebSocket(WS_URL)

        ws.onopen = () => {
          setStatus('recording')
        }

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)

            if (msg.status === 'ready') {
              return
            }

            if (msg.type === 'response' && msg.data?.result) {
              const result = msg.data.result
              if (result.text) {
                onTextUpdateRef.current?.(result.text, result.is_endpoint || false)
              }
            }

            if (msg.type === 'error') {
              setError(msg.error || 'Ошибка транскрибации')
              setStatus('error')
            }
          } catch {
            // Ignore parse errors
          }
        }

        ws.onerror = () => {
          setError('Ошибка подключения к серверу')
          setStatus('error')
        }

        ws.onclose = () => {
          if (status !== 'error') {
            setStatus('disconnected')
          }
        }

        wsRef.current = ws
      } catch (e) {
        console.error('Failed to start recording:', e)
        setError(e instanceof Error ? e.message : 'Не удалось получить доступ к микрофону')
        setStatus('error')
      }
    },
    [status]
  )

  return { status, error, startRecording, stopRecording }
}
