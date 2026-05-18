import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Container,
  Title,
  Text,
  Stack,
  Card,
  Group,
  ActionIcon,
  Menu,
  SimpleGrid,
  Box,
  Badge,
} from '@mantine/core'
import {
  IconDotsVertical,
  IconArrowLeft,
  IconThermometer,
  IconHeart,
  IconHeartbeat,
  IconScale,
  IconRuler,
  IconDroplet,
  IconNotes,
} from '@tabler/icons-react'
import { mockPatients } from '../data/mockPatients'
import { NotesModal } from '../components/NotesModal'

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function PatientPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [notesOpened, setNotesOpened] = useState(false)

  const patient = mockPatients.find((p) => p.id === id)

  if (!patient) {
    return (
      <Container size="sm" px="sm" py="md">
        <Text ta="center">Пациент не найден</Text>
      </Container>
    )
  }

  return (
    <Container size="sm" px="sm" py="md">
      <Stack gap="md">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs" wrap="nowrap">
            <ActionIcon variant="subtle" onClick={() => navigate(-1)}>
              <IconArrowLeft size={22} />
            </ActionIcon>
            <Box style={{ flex: 1, minWidth: 0 }}>
              <Title order={4} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {patient.fullName}
              </Title>
              <Text size="sm" c="dimmed">
                {patient.age} лет ({formatDate(patient.dateOfBirth)})
              </Text>
            </Box>
          </Group>
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <ActionIcon variant="subtle" size="lg">
                <IconDotsVertical size={22} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item
                leftSection={<IconNotes size={18} />}
                onClick={() => setNotesOpened(true)}
              >
                Заметки к ИБ
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>

        <Card withBorder p="sm">
          <Stack gap={4}>
            <Text fw={700} size="sm" c="dimmed">
              История болезни
            </Text>
            <Text fw={600}>
              № {patient.medicalRecordNumber}
            </Text>
            <Text size="sm">
              Поступил: {formatDate(patient.admissionDate)}
            </Text>
            <Text size="sm">
              Диагноз при поступлении: {patient.admissionDiagnosis}
            </Text>
            <Text size="sm">
              Клинический диагноз: {patient.clinicalDiagnosis}
            </Text>
            <Badge variant="light" size="sm" style={{ alignSelf: 'flex-start' }}>
              {patient.severity}
            </Badge>
          </Stack>
        </Card>

        <SimpleGrid cols={2} spacing="sm">
          <Card withBorder p="sm">
            <Stack gap="sm">
              <Text fw={700} size="sm" c="dimmed">
                Показатели здоровья
              </Text>
              <Group gap="xs" wrap="nowrap">
                <IconThermometer size={18} />
                <Box>
                  <Text size="xs" c="dimmed">Температура</Text>
                  <Text fw={500}>{patient.healthIndicators.temperature} °C</Text>
                </Box>
              </Group>
              <Group gap="xs" wrap="nowrap">
                <IconHeartbeat size={18} />
                <Box>
                  <Text size="xs" c="dimmed">Давление</Text>
                  <Text fw={500}>{patient.healthIndicators.bloodPressure}</Text>
                </Box>
              </Group>
              <Group gap="xs" wrap="nowrap">
                <IconHeart size={18} />
                <Box>
                  <Text size="xs" c="dimmed">Сердцебиение</Text>
                  <Text fw={500}>{patient.healthIndicators.heartRate} уд/мин</Text>
                </Box>
              </Group>
            </Stack>
          </Card>

          <Card withBorder p="sm">
            <Stack gap="sm">
              <Group gap="xs" wrap="nowrap">
                <IconDroplet size={18} />
                <Box>
                  <Text size="xs" c="dimmed">Группа крови</Text>
                  <Text fw={500}>{patient.bloodGroup}</Text>
                </Box>
              </Group>
              <Box style={{ borderTop: '1px solid #e9ecef', margin: '4px 0' }} />
              <Text fw={700} size="sm" c="dimmed">
                Антропометрия
              </Text>
              <Group gap="xs" wrap="nowrap">
                <IconRuler size={18} />
                <Box>
                  <Text size="xs" c="dimmed">Рост</Text>
                  <Text fw={500}>{patient.anthropometry.height} см</Text>
                </Box>
              </Group>
              <Group gap="xs" wrap="nowrap">
                <IconScale size={18} />
                <Box>
                  <Text size="xs" c="dimmed">Вес</Text>
                  <Text fw={500}>{patient.anthropometry.weight} кг</Text>
                </Box>
              </Group>
              <Text size="sm" c="dimmed" ta="right">
                ИМТ: {patient.anthropometry.bmi} кг/м²
              </Text>
            </Stack>
          </Card>
        </SimpleGrid>
      </Stack>

      <NotesModal
        opened={notesOpened}
        onClose={() => setNotesOpened(false)}
        medicalRecordNumber={patient.medicalRecordNumber}
      />
    </Container>
  )
}
