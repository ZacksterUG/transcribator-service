import { useState, useEffect } from 'react';
import { Container, Title, Text, Stack, Card, Group, ThemeIcon, Badge, Button, Box, Loader, Center } from '@mantine/core';
import { IconCheck, IconCopy, IconAlertCircle } from '@tabler/icons-react';
import { useParams } from 'react-router-dom';

interface JobResult {
  job_id: string;
  status: string;
  results?: Array<{
    segments?: Array<{
      text: string;
      start: number;
      end: number;
    }>;
    error?: string;
  }>;
  error?: string;
  message?: string;
}

export function AsyncResultPage() {
  const { jobId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const response = await fetch(`http://localhost:3001/api/async/job/${jobId}`);
        
        const data = await response.json();
        console.log('Result data:', data);
        
        setResult(data);
        
        if (data.status === 'failed' || data.error) {
          setError(data.message || data.error || 'Ошибка при транскрибации');
        }
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (jobId) {
      fetchResult();
    }
  }, [jobId]);

  if (loading) {
    return (
      <Center h="50vh">
        <Loader size="lg" />
      </Center>
    );
  }

  if (error) {
    return (
      <Container size="lg" py="xl">
        <Card padding="xl" radius="md" withBorder color="red">
          <Group>
            <ThemeIcon size={48} radius="md" color="red">
              <IconAlertCircle size={24} />
            </ThemeIcon>
            <Box>
              <Title order={3}>Ошибка</Title>
              <Text c="dimmed">{error}</Text>
            </Box>
          </Group>
        </Card>
        <Button mt="lg" onClick={() => window.location.href = '/'}>
          Назад к загрузке
        </Button>
      </Container>
    );
  }

  const textSegments = result?.results?.[0]?.segments || [];
  const fullText = textSegments.map(s => s.text).join(' ');

  return (
    <Container size="lg" py="xl">
      <Stack gap="xl">
        <Group>
          <ThemeIcon size={48} radius="md" variant="light" color="green">
            <IconCheck size={24} />
          </ThemeIcon>
          <Box>
            <Title order={2}>Результат транскрибации</Title>
            <Text c="dimmed">ID задачи: {jobId}</Text>
          </Box>
        </Group>

        <Card padding="xl" radius="md" withBorder>
          <Stack gap="md">
            <Group justify="space-between">
              <Badge color={result?.status === 'finished' ? 'green' : 'yellow'} size="lg">
                {result?.status === 'finished' ? 'Завершено' : result?.status}
              </Badge>
              {fullText && (
                <Button variant="light" size="xs" leftSection={<IconCopy size={14} />} onClick={() => navigator.clipboard.writeText(fullText)}>
                  Копировать
                </Button>
              )}
            </Group>
            
            {fullText ? (
              <Box 
                p="md" 
                bg="var(--mantine-color-dark-6)" 
                style={{ borderRadius: 8, maxHeight: 500, overflow: 'auto' }}
              >
                <Text size="sm" fw={500} mb="md">Текст транскрибации:</Text>
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{fullText}</Text>
              </Box>
            ) : (
              <Text c="dimmed">Нет текста для отображения</Text>
            )}

            {textSegments.length > 0 && (
              <Box>
                <Text size="sm" fw={500} mb="xs">Сегменты ({textSegments.length}):</Text>
                <Stack gap="xs" maw={600}>
                  {textSegments.slice(0, 10).map((seg, i) => (
                    <Box key={i} p="xs" bg="var(--mantine-color-dark-5)" style={{ borderRadius: 4 }}>
                      <Text size="xs" c="dimmed">[{seg.start.toFixed(2)}s - {seg.end.toFixed(2)}s]</Text>
                      <Text size="sm">{seg.text}</Text>
                    </Box>
                  ))}
                  {textSegments.length > 10 && (
                    <Text size="sm" c="dimmed">... и ещё {textSegments.length - 10} сегментов</Text>
                  )}
                </Stack>
              </Box>
            )}
          </Stack>
        </Card>

        <Group>
          <Button variant="light" onClick={() => window.location.href = '/'}>
            Новая транскрибация
          </Button>
          <Button variant="light" onClick={() => window.location.href = '/'}>
            На главную
          </Button>
        </Group>
      </Stack>
    </Container>
  );
}