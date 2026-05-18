import { useState } from 'react'
import {
  Drawer,
  Stack,
  Text,
  Group,
  ActionIcon,
  Box,
  Divider,
  Button,
  ScrollArea,
} from '@mantine/core'
import { IconPlus, IconEdit, IconTrash } from '@tabler/icons-react'
import { mockNotes } from '../data/mockPatients'
import type { Note } from '../types'
import { NoteEditorModal } from './NoteEditorModal'

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

interface NotesModalProps {
  opened: boolean
  onClose: () => void
  medicalRecordNumber: string
}

export function NotesModal({ opened, onClose, medicalRecordNumber }: NotesModalProps) {
  const [editorOpened, setEditorOpened] = useState(false)
  const [editingNote, setEditingNote] = useState<Note | null>(null)
  const [notes, setNotes] = useState<Note[]>(mockNotes)

  const patientNotes = notes.filter(
    (note) => note.medicalRecordNumber === medicalRecordNumber
  )

  const handleAddNote = () => {
    setEditingNote(null)
    setEditorOpened(true)
  }

  const handleEditNote = (note: Note) => {
    setEditingNote(note)
    setEditorOpened(true)
  }

  const handleDeleteNote = (note: Note) => {
    setEditingNote(note)
    setEditorOpened(true)
  }

  const handleSaveNote = (text: string) => {
    if (editingNote) {
      if (text.trim() === '') {
        setNotes((prev) => prev.filter((n) => n.id !== editingNote.id))
      } else {
        setNotes((prev) =>
          prev.map((n) => (n.id === editingNote.id ? { ...n, text } : n))
        )
      }
    } else {
      const newNote: Note = {
        id: Date.now().toString(),
        medicalRecordNumber,
        createdAt: new Date().toISOString(),
        doctor: 'Текущий врач',
        department: 'Кардиологическое',
        text,
      }
      setNotes((prev) => [newNote, ...prev])
    }
    setEditorOpened(false)
    setEditingNote(null)
  }

  return (
    <>
      <Drawer
        opened={opened}
        onClose={onClose}
        title={
          <Text fw={700} size="lg">
            Заметки к ИБ: {medicalRecordNumber}
          </Text>
        }
        size="100%"
        position="bottom"
        styles={{
          body: { padding: 0 },
          content: { borderRadius: '16px 16px 0 0', height: '60vh' },
          header: { padding: '16px 20px' },
        }}
        withCloseButton={false}
        overlayProps={{ backgroundOpacity: 0.4 }}
      >
        <Box style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Box p="sm" style={{ borderBottom: '1px solid #e9ecef' }}>
            <Button
              fullWidth
              leftSection={<IconPlus size={18} />}
              onClick={handleAddNote}
              size="md"
            >
              Добавить заметку
            </Button>
          </Box>

          <ScrollArea style={{ flex: 1 }}>
            <Stack gap={0} p="sm">
              {patientNotes.map((note, index) => (
                <Box key={note.id}>
                  {index > 0 && <Divider my="sm" />}
                  <Group justify="space-between" wrap="nowrap" mb="xs">
                    <Box style={{ flex: 1, minWidth: 0 }}>
                      <Text size="xs" c="dimmed">
                        {formatDateTime(note.createdAt)} | {note.doctor} | {note.department}
                      </Text>
                    </Box>
                    <Group gap={4}>
                      <ActionIcon variant="subtle" size="sm" onClick={() => handleEditNote(note)}>
                        <IconEdit size={16} />
                      </ActionIcon>
                      <ActionIcon variant="subtle" size="sm" color="red" onClick={() => handleDeleteNote(note)}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  </Group>
                  <Text size="sm">{note.text}</Text>
                </Box>
              ))}

              {patientNotes.length === 0 && (
                <Text ta="center" c="dimmed" py="xl">
                  Заметок пока нет
                </Text>
              )}
            </Stack>
          </ScrollArea>
        </Box>
      </Drawer>

      <NoteEditorModal
        opened={editorOpened}
        onClose={() => {
          setEditorOpened(false)
          setEditingNote(null)
        }}
        onSave={handleSaveNote}
        note={editingNote}
        medicalRecordNumber={medicalRecordNumber}
      />
    </>
  )
}
