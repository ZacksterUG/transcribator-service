import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Container,
  Title,
  TextInput,
  Stack,
  Card,
  Text,
  Group,
  Badge,
  Box,
} from '@mantine/core'
import { IconSearch, IconBed, IconBuildingHospital } from '@tabler/icons-react'
import { mockPatients } from '../data/mockPatients'

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function PatientsPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const filteredPatients = mockPatients.filter((patient) =>
    patient.fullName.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <Container size="sm" px="sm" py="md">
      <Stack gap="md">
        <Title order={3} ta="center">Журнал пациентов</Title>

        <TextInput
          placeholder="Поиск по ФИО"
          leftSection={<IconSearch size={18} />}
          value={search}
          onChange={(e) => setSearch(e.currentTarget.value)}
          size="md"
        />

        <Stack gap="sm">
          {filteredPatients.map((patient) => (
            <Card
              key={patient.id}
              withBorder
              p="sm"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/patient/${patient.id}`)}
            >
              <Stack gap={4}>
                <Group justify="space-between" wrap="nowrap">
                  <Text fw={700} size="sm">
                    ИБ: {patient.medicalRecordNumber}
                  </Text>
                  <Group gap="xs" wrap="nowrap">
                    <Badge size="sm" variant="light" leftSection={<IconBuildingHospital size={12} />}>
                      Палата {patient.ward}
                    </Badge>
                    <Badge size="sm" variant="light" leftSection={<IconBed size={12} />}>
                      Койка {patient.bed}
                    </Badge>
                  </Group>
                </Group>

                <Text fw={600} size="md">
                  {patient.fullName}
                </Text>

                <Text size="sm" c="dimmed">
                  {patient.age} лет ({formatDate(patient.dateOfBirth)})
                </Text>

                <Box style={{ borderTop: '1px solid #e9ecef', margin: '4px 0' }} />

                <Text size="sm">
                  В стационаре с: {formatDate(patient.hospitalizationDate)} | В отделении с: {formatDate(patient.departmentDate)}
                </Text>

                <Text size="sm" fw={500}>
                  Диагноз: {patient.diagnosis} ({patient.icdCode})
                </Text>

                <Text size="sm" c="dimmed">
                  Лечащий врач: {patient.attendingDoctor}
                </Text>
              </Stack>
            </Card>
          ))}

          {filteredPatients.length === 0 && (
            <Text ta="center" c="dimmed" py="xl">
              Пациенты не найдены
            </Text>
          )}
        </Stack>
      </Stack>
    </Container>
  )
}
