import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Drawer,
  Stack,
  Text,
  Textarea,
  Group,
  Button,
  Box,
  ActionIcon,
  Badge,
} from '@mantine/core'
import { IconMicrophone, IconMicrophoneOff } from '@tabler/icons-react'
import type { Note } from '../types'
import { useVoiceTranscription } from '../hooks/useVoiceTranscription'

function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface NoteEditorModalProps {
  opened: boolean
  onClose: () => void
  onSave: (text: string) => void
  note: Note | null
  medicalRecordNumber: string
}

export function NoteEditorModal({
  opened,
  onClose,
  onSave,
  note,
  medicalRecordNumber,
}: NoteEditorModalProps) {
  const committedRef = useRef('')
  const pendingRef = useRef('')
  const insertPosRef = useRef(0)
  const [displayText, setDisplayText] = useState('')
  const [isRecordingUi, setIsRecordingUi] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isRecordingRef = useRef(false)
  const openedRef = useRef(false)

  const { status, error, startRecording, stopRecording } = useVoiceTranscription()

  useEffect(() => {
    openedRef.current = opened
  }, [opened])

  useEffect(() => {
    if (opened) {
      const initial = note?.text || ''
      committedRef.current = initial
      pendingRef.current = ''
      insertPosRef.current = initial.length
      setDisplayText(initial)
    }
  }, [opened, note])

  const flushDisplay = useCallback(() => {
    setDisplayText(committedRef.current + pendingRef.current)
  }, [])

  const handleTextUpdate = useCallback((text: string, isFinal: boolean) => {
    if (isFinal) {
      let finalized = text
      if (finalized.trim() && !finalized.trimEnd().endsWith('.')) {
        finalized = finalized.trimEnd() + '. '
      } else if (finalized.trim()) {
        finalized = finalized + ' '
      }

      const pos = insertPosRef.current
      const before = committedRef.current.slice(0, pos)
      const after = committedRef.current.slice(pos)

      let processed = finalized
      if (before.length === 0 || before.trimEnd().endsWith('.')) {
        processed = processed.charAt(0).toUpperCase() + processed.slice(1)
      }

      committedRef.current = before + processed + after
      insertPosRef.current = pos + processed.length
      pendingRef.current = ''
      flushDisplay()

      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = insertPosRef.current
          textareaRef.current.selectionEnd = insertPosRef.current
        }
      }, 0)
    } else {
      pendingRef.current = text
      flushDisplay()
    }
  }, [flushDisplay])

  const handleMicrophoneClick = async () => {
    if (isRecordingRef.current) {
      stopRecording()
      isRecordingRef.current = false
      setIsRecordingUi(false)
      pendingRef.current = ''
      flushDisplay()
    } else {
      const pos = textareaRef.current?.selectionStart ?? committedRef.current.length
      insertPosRef.current = pos
      isRecordingRef.current = true
      setIsRecordingUi(true)
      pendingRef.current = ''
      await startRecording(handleTextUpdate)
    }
  }

  useEffect(() => {
    return () => {
      if (isRecordingRef.current) {
        stopRecording()
      }
    }
  }, [stopRecording])

  const handleTextChange = (value: string) => {
    committedRef.current = value
    pendingRef.current = ''
    setDisplayText(value)
  }

  const handleSelectionChange = () => {
    if (textareaRef.current && !isRecordingRef.current) {
      insertPosRef.current = textareaRef.current.selectionStart ?? committedRef.current.length
    }
  }

  const handleSave = () => {
    const finalText = committedRef.current + pendingRef.current
    onSave(finalText)
    onClose()
  }

  const handleCancel = () => {
    if (isRecordingRef.current) {
      stopRecording()
      isRecordingRef.current = false
    }
    onClose()
  }

  const isRecording = status === 'recording' || isRecordingUi

  return (
    <Drawer
      opened={opened}
      onClose={handleCancel}
      title={
        <Stack gap={2}>
          <Text fw={700} size="lg">
            Заметка к ИБ: {medicalRecordNumber}
          </Text>
          {note && (
            <Text size="xs" c="dimmed">
              {formatDateTime(note.createdAt)} | {note.doctor} | {note.department}
            </Text>
          )}
        </Stack>
      }
      size="100%"
      position="bottom"
      styles={{
        body: { padding: '16px 20px' },
        content: { borderRadius: '16px 16px 0 0', height: '60vh' },
        header: { padding: '16px 20px' },
      }}
      withCloseButton={false}
      overlayProps={{ backgroundOpacity: 0.4 }}
    >
      <Stack gap="md" style={{ height: '100%' }}>
        <Box style={{ position: 'relative', flex: 1 }}>
          <Textarea
            ref={textareaRef}
            placeholder="Введите текст заметки..."
            value={displayText}
            onChange={(e) => handleTextChange(e.currentTarget.value)}
            onSelect={handleSelectionChange}
            onClick={handleSelectionChange}
            onKeyUp={handleSelectionChange}
            autosize
            minRows={10}
            maxRows={15}
            size="md"
            styles={{
              input: {
                paddingRight: 60,
                resize: 'none',
                minHeight: '200px',
              },
            }}
          />
          <ActionIcon
            size="lg"
            radius="xl"
            color={isRecording ? 'red' : 'gray'}
            variant={isRecording ? 'filled' : 'light'}
            style={{
              position: 'absolute',
              right: 8,
              bottom: 8,
            }}
            onClick={handleMicrophoneClick}
            disabled={status === 'connecting'}
          >
            {isRecording ? <IconMicrophoneOff size={20} /> : <IconMicrophone size={20} />}
          </ActionIcon>
        </Box>

        {isRecording && (
          <Group gap="xs">
            <Badge color="red" size="sm">
              Запись...
            </Badge>
            <Text size="xs" c="dimmed">
              Говорите четко в микрофон
            </Text>
          </Group>
        )}

        {error && (
          <Text size="sm" c="red">
            {error}
          </Text>
        )}

        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={handleCancel}>
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={!displayText.trim()}>
            {note ? 'Сохранить' : 'Создать'}
          </Button>
        </Group>
      </Stack>
    </Drawer>
  )
}
