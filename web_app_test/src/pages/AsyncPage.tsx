import { useState, useEffect } from 'react';
import { Container, Title, Text, Stack, Card, Group, ThemeIcon, Badge, Button, FileButton, Checkbox, TextInput, Box, Progress, List, Alert } from '@mantine/core';
import { IconFileMusic, IconUpload, IconBrandTelegram, IconCheck, IconArrowRight, IconArrowLeft, IconPlayerPlay } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';
import { keycloak } from '../config/keycloak';

const STORAGE_KEY = 'transcriber_telegram_id';

export function AsyncPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [sendToTelegram, setSendToTelegram] = useState(false);
  const [telegramUserId, setTelegramUserId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [telegramMessage, setTelegramMessage] = useState(false);

  useEffect(() => {
    const savedId = localStorage.getItem(STORAGE_KEY);
    if (savedId) {
      setTelegramUserId(savedId);
      setSendToTelegram(true);
    }
  }, []);

  const handleSubmit = async () => {
    if (!file) return;
    if (sendToTelegram && !telegramUserId.trim()) return;
    
    setIsSubmitting(true);
    
    try {
      const formData = new FormData();
      formData.append('audio', file);
      formData.append('send_to_telegram', sendToTelegram ? 'true' : 'false');
      if (sendToTelegram && telegramUserId) {
        formData.append('telegram_user_id', telegramUserId);
      }
      
      const token = keycloak.instance.token;
      console.log('Token:', token ? token.substring(0, 50) + '...' : 'no token');
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/async/job`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData,
      });
      
      const data = await response.json();
      console.log('Job created, response:', data);
      
      if (data.job_id) {
        setJobId(data.job_id);
        
        if (sendToTelegram && telegramUserId) {
          localStorage.setItem(STORAGE_KEY, telegramUserId);
          setTelegramMessage(true);
        } else {
          setSubmitted(true);
        }
      } else if (data.jobs && data.jobs.length > 0) {
        const actualJobId = data.jobs[0].id || data.jobs[0].job_id;
        setJobId(actualJobId);
        if (sendToTelegram && telegramUserId) {
          setTelegramMessage(true);
        } else {
          setSubmitted(true);
        }
      }
    } catch (error) {
      console.error('Error creating job:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted && jobId) {
    return (
      <Container size="lg" py="xl">
        <Stack gap="xl">
          <Group>
            <ThemeIcon size={48} radius="md" variant="light" color="blue">
              <IconFileMusic size={24} />
            </ThemeIcon>
            <Box>
              <Title order={2}>Ожидание результата</Title>
              <Text c="dimmed">ID задачи: {jobId}</Text>
            </Box>
          </Group>

          <ProgressJob jobId={jobId} />
          
          <Button variant="light" onClick={() => {
              const savedId = localStorage.getItem(STORAGE_KEY);
              setFile(null);
              setSendToTelegram(false);
              setTelegramUserId(savedId || '');
              setSendToTelegram(!!savedId);
              setSubmitted(false);
              setJobId(null);
              navigate('/async');
            }}>
            Назад к загрузке
          </Button>
        </Stack>
      </Container>
    );
  }

  if (telegramMessage) {
    return (
      <Container size="sm" py="xl">
        <Stack gap="lg" align="center">
          <ThemeIcon size={80} radius="md" color="green">
            <IconCheck size={40} />
          </ThemeIcon>
          
          <Title order={2} ta="center">Задача создана!</Title>
          
          <Alert color="blue" title="Результат будет отправлен в Telegram">
            <Text size="sm">
              После завершения транскрибации результат будет отправлен 
              вашему боту в Telegram. ID пользователя: <Text fw={700} span>{telegramUserId}</Text>
            </Text>
          </Alert>
          
          <Group>
            <Button variant="light" leftSection={<IconArrowLeft size={16} />} onClick={() => {
              const savedId = localStorage.getItem(STORAGE_KEY);
              setFile(null);
              setSendToTelegram(false);
              setTelegramUserId(savedId || '');
              setSendToTelegram(!!savedId);
              setTelegramMessage(false);
              setSubmitted(false);
              setJobId(null);
              navigate('/async');
            }}>
              Загрузить ещё файл
            </Button>
            <Button leftSection={<IconPlayerPlay size={16} />} onClick={() => {
              setTelegramMessage(false);
              if (jobId) {
                setSubmitted(true);
              }
            }}>
              Отслеживать статус
            </Button>
          </Group>
        </Stack>
      </Container>
    );
  }

  return (
    <Container size="md" py="xl">
      <Stack gap="xl">
        <Group>
          <ThemeIcon size={48} radius="md" variant="light" color="blue">
            <IconFileMusic size={24} />
          </ThemeIcon>
          <Box>
            <Title order={2}>Асинхронная обработка</Title>
            <Text c="dimmed">Загрузка аудиофайла для транскрибации</Text>
          </Box>
        </Group>

        <Card padding="xl" radius="md" withBorder>
          <Stack gap="lg">
            <Box>
              <Text fw={500} mb="xs">Выберите аудиофайл</Text>
              <FileButton onChange={setFile} accept="audio/*,.mp3,.wav,.flac,.ogg,.m4a">
                {(props) => (
                  <Button 
                    {...props} 
                    variant="light" 
                    leftSection={<IconUpload size={18} />}
                    fullWidth
                  >
                    {file ? file.name : 'Выбрать файл'}
                  </Button>
                )}
              </FileButton>
              {file && (
                <Text size="sm" c="dimmed" mt="xs">
                  Размер: {(file.size / 1024 / 1024).toFixed(2)} МБ
                </Text>
              )}
            </Box>

            <Checkbox
              label={
                <Group gap="xs">
                  <IconBrandTelegram size={16} />
                  <Text>Отправить результат в Telegram</Text>
                </Group>
              }
              checked={sendToTelegram}
              onChange={(event) => setSendToTelegram(event.currentTarget.checked)}
            />

            {sendToTelegram && (
              <Box pl={28}>
                <Box pl={28} mb="md">
                  <Text size="sm" c="dimmed" mb="xs">
                    После завершения транскрибации бот отправит вам результат.{' '}
                    <Text component="a" href="https://t.me/transcriberwebhooktestbot" target="_blank" c="blue">
                      @transcriberwebhooktestbot
                    </Text>
                  </Text>
                  <TextInput
                    placeholder="Ваш Telegram ID"
                    value={telegramUserId}
                    onChange={(event) => setTelegramUserId(event.currentTarget.value)}
                    description="Нажмите /start в боте для получения ID"
                  />
                </Box>
              </Box>
            )}

            <Button
              fullWidth
              size="lg"
              leftSection={<IconFileMusic size={20} />}
              onClick={handleSubmit}
              disabled={!file || isSubmitting || (sendToTelegram && !telegramUserId.trim())}
              loading={isSubmitting}
            >
              Начать транскрибацию
            </Button>
          </Stack>
        </Card>

        <Card padding="md" radius="md" withBorder>
          <Text size="sm" fw={500} mb="xs">Поддерживаемые форматы:</Text>
          <Group gap="xs">
            {['MP3', 'WAV', 'FLAC', 'OGG', 'M4A'].map(format => (
              <Badge key={format} variant="light">{format}</Badge>
            ))}
          </Group>
        </Card>
      </Stack>
    </Container>
  );
}

function ProgressJob({ jobId }: { jobId: string }) {
  const [status, setStatus] = useState<'uploading' | 'transcribing' | 'completed' | 'failed'>('uploading');
  const [error, setError] = useState<string | null>(null);
  
  const navigate = useNavigate();

  useEffect(() => {
    let mounted = true;
    
    const checkStatus = async () => {
      if (!mounted) return;
      
      try {
        console.log('Checking status for:', jobId);
        const token = keycloak.instance.token;
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/async/job/${jobId}`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
        const data = await response.json();
        console.log('Status response:', data);
        
        if (data.status === 'completed' || data.status === 'finished') {
          setStatus('completed');
        } else if (data.status === 'failed' || data.status === 'error') {
          setStatus('failed');
          setError(data.error || 'Ошибка при транскрибации');
        } else if (data.status === 'in_progress' || data.status === 'transcribing' || data.status === 'processing') {
          setStatus('transcribing');
          console.log('Status is in_progress, polling again in 2s...');
          setTimeout(() => {
            if (mounted) checkStatus();
          }, 2000);
        } else {
          console.log('Unknown status, polling again...', data.status);
          setTimeout(() => {
            if (mounted) checkStatus();
          }, 3000);
        }
      } catch (err: any) {
        console.error('Error checking status:', err);
        setTimeout(() => {
          if (mounted) checkStatus();
        }, 3000);
      }
    };

    checkStatus();
    
    return () => {
      mounted = false;
    };
  }, [jobId]);

  const steps = [
    { key: 'uploading', label: 'Загрузка файла', icon: IconUpload },
    { key: 'transcribing', label: 'Транскрибация', icon: IconFileMusic },
    { key: 'completed', label: 'Завершено', icon: IconCheck },
  ];

  const activeIndex = steps.findIndex(s => s.key === status);
  const isFailed = status === 'failed';

  return (
    <Card padding="lg" radius="md" withBorder>
      <Stack gap="lg">
        <Group>
          <Text fw={600}>Статус обработки</Text>
          <Badge color={isFailed ? 'red' : 'green'}>
            {isFailed ? 'Ошибка' : status === 'completed' ? 'Завершено' : 'В процессе'}
          </Badge>
        </Group>

        <Progress value={(activeIndex + 1) / steps.length * 100} size="lg" animated={status !== 'completed'} />

        <List spacing="md">
          {steps.map((step, index) => (
            <List.Item
              key={step.key}
              icon={
                <ThemeIcon 
                  size={24} 
                  radius="xl" 
                  color={index <= activeIndex ? 'green' : 'gray'}
                  variant={index <= activeIndex ? 'filled' : 'light'}
                >
                  <step.icon size={14} />
                </ThemeIcon>
              }
            >
              <Text 
                c={index <= activeIndex ? undefined : 'dimmed'}
                fw={index === activeIndex ? 600 : 400}
              >
                {step.label}
                {index === activeIndex && status === 'transcribing' && '...'}
              </Text>
            </List.Item>
          ))}
        </List>

        {error && (
          <Alert color="red" title="Ошибка">
            {error}
          </Alert>
        )}

        {status === 'completed' && (
          <Button leftSection={<IconArrowRight size={16} />} onClick={() => navigate(`/async/result/${jobId}`)}>
            Посмотреть результат
          </Button>
        )}
      </Stack>
    </Card>
  );
}