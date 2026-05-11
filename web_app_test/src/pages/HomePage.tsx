import { Container, Title, Text, Stack, Group, Badge, Box, Button, Grid, Card, ThemeIcon, List, Code, Table } from '@mantine/core';
import { 
  IconMicrophone, IconFileMusic, IconCloud, IconApiApp, 
  IconServer, IconDatabase, IconKey, IconStack2, IconDeviceDesktop, 
  IconCheck, IconClock, IconArrowRight, IconLock, IconMessage, IconFile
} from '@tabler/icons-react';

export function HomePage() {
  return (
    <Box>
      <Container size="lg" pt={50} pb={60}>
        <Stack gap={50}>
          <Stack gap={20} ta="center">
            <Title order={1} size={48} fw={700}>
              Система Транскрибации Речи
            </Title>
            <Text size="xl" c="dimmed" maw={800} mx="auto">
              Распределённая микросервисная архитектура для распознавания речи с поддержкой 
              асинхронной пакетной обработки и синхронной потоковой транскрибации в реальном времени
            </Text>
          </Stack>

          <Group justify="center" gap="xs" wrap="wrap">
            <Badge size="lg" variant="light" color="blue">Go + Gin</Badge>
            <Badge size="lg" variant="light" color="green">Faster-Whisper</Badge>
            <Badge size="lg" variant="light" color="grape">Sherpa-ONNX</Badge>
            <Badge size="lg" variant="light" color="orange">NATS JetStream</Badge>
            <Badge size="lg" variant="light" color="red">PostgreSQL</Badge>
            <Badge size="lg" variant="light" color="teal">MinIO</Badge>
            <Badge size="lg" variant="light" color="violet">Keycloak</Badge>
            <Badge size="lg" variant="light" color="pink">Redis</Badge>
          </Group>

          {/* Overview Section */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">Общее описание</Title>
              <Grid gap="xl">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Group>
                      <ThemeIcon variant="light" color="blue" size="xl" radius="md">
                        <IconFileMusic size={24} />
                      </ThemeIcon>
                      <Box>
                        <Text fw={600} size="lg">Асинхронная обработка</Text>
                        <Text size="sm" c="dimmed">transcribator-async</Text>
                      </Box>
                    </Group>
                    <Text c="dimmed">
                      Предназначен для обработки аудиофайлов в фоновом режиме. Идеален для пакетной 
                      обработки больших объёмов записей, архивов и длинных аудиофайлов.
                    </Text>
                    <List spacing="xs" size="sm">
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Модели:</Text> Faster-Whisper (локально), Croc API (облако)</Text>
                      </List.Item>
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Input:</Text> Файл, архив (.zip), список файлов</Text>
                      </List.Item>
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Output:</Text> Сегменты с timestamps, токены, слова</Text>
                      </List.Item>
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Гарантия:</Text> At-least-once доставка</Text>
                      </List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Group>
                      <ThemeIcon variant="light" color="green" size="xl" radius="md">
                        <IconMicrophone size={24} />
                      </ThemeIcon>
                      <Box>
                        <Text fw={600} size="lg">Потоковая обработка</Text>
                        <Text size="sm" c="dimmed">transcribator-sync</Text>
                      </Box>
                    </Group>
                    <Text c="dimmed">
                      Обрабатывает аудиопоток в реальном времени с минимальной задержкой. 
                      Подходит для live-трансляций, телефонных звонков, голосового ввода.
                    </Text>
                    <List spacing="xs" size="sm">
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Модели:</Text> sherpa-onnx (Vosk-compatible)</Text>
                      </List.Item>
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Input:</Text> Аудио-чанки (base64, float32, 16kHz)</Text>
                      </List.Item>
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Output:</Text> Промежуточные результаты + endpoint</Text>
                      </List.Item>
                      <List.Item>
                        <Text size="sm"><Text fw={500} span>Задержка:</Text> ~160ms на чанк</Text>
                      </List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
              </Grid>
            </Stack>
          </Card>

          {/* API Endpoints */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">API Endpoints</Title>
              <Text c="dimmed" ta="center">
                Все endpoints требуют авторизацию через JWT токен. Токен получается через Keycloak 
                и должен передаваться в заголовке <Code>Authorization: Bearer &lt;token&gt;</Code>
              </Text>
              
              <Table striped highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Метод</Table.Th>
                    <Table.Th>Путь</Table.Th>
                    <Table.Th>Описание</Table.Th>
                    <Table.Th>Роль</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  <Table.Tr>
                    <Table.Td><Code color="blue">POST</Code></Table.Td>
                    <Table.Td><Code>/api/async/job</Code></Table.Td>
                    <Table.Td>Создание задачи транскрибации</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">GET</Code></Table.Td>
                    <Table.Td><Code>/api/async/job/:job_id</Code></Table.Td>
                    <Table.Td>Получение статуса задачи</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">GET</Code></Table.Td>
                    <Table.Td><Code>/api/async/job/:job_id/result</Code></Table.Td>
                    <Table.Td>Получение результата транскрибации</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">GET</Code></Table.Td>
                    <Table.Td><Code>/api/async/jobs</Code></Table.Td>
                    <Table.Td>Список задач пользователя</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">POST</Code></Table.Td>
                    <Table.Td><Code>/api/sync/session</Code></Table.Td>
                    <Table.Td>Создание сессии потоковой транскрибации</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">GET</Code></Table.Td>
                    <Table.Td><Code>/api/sync/session/:session_id/status</Code></Table.Td>
                    <Table.Td>Получение статуса сессии</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">GET</Code></Table.Td>
                    <Table.Td><Code>/api/sync/sessions</Code></Table.Td>
                    <Table.Td>Список активных сессий</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">POST</Code></Table.Td>
                    <Table.Td><Code>/api/webhooks</Code></Table.Td>
                    <Table.Td>Регистрация webhook URL</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">GET</Code></Table.Td>
                    <Table.Td><Code>/api/webhooks</Code></Table.Td>
                    <Table.Td>Список зарегистрированных webhook</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td><Code color="blue">DELETE</Code></Table.Td>
                    <Table.Td><Code>/api/webhooks/:id</Code></Table.Td>
                    <Table.Td>Удаление webhook</Table.Td>
                    <Table.Td>transcriber</Table.Td>
                  </Table.Tr>
                </Table.Tbody>
              </Table>
            </Stack>
          </Card>

          {/* Services Architecture */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">Сервисы и архитектура</Title>
              
              <Grid gap="lg">
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="blue" size="lg" radius="md">
                          <IconApiApp size={20} />
                        </ThemeIcon>
                        <Text fw={600}>API Gateway</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Центральная точка входа. Реализован на Go с использованием Gin framework.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Маршрутизация запросов</List.Item>
                        <List.Item>JWT авторизация</List.Item>
                        <List.Item>Валидация запросов</List.Item>
                        <List.Item>Интеграция с NATS</List.Item>
                        <List.Item>Интеграция с MinIO</List.Item>
                        <List.Item>Webhook уведомления</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Port: 10000</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="green" size="lg" radius="md">
                          <IconServer size={20} />
                        </ThemeIcon>
                        <Text fw={600}>Async Service</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Асинхронный сервис обработки аудио. Реализован на Python.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Faster-Whisper модель</List.Item>
                        <List.Item>Поддержка Croc API</List.Item>
                        <List.Item>NATS consumer</List.Item>
                        <List.Item>Идемпотентность</List.Item>
                        <List.Item>Graceful shutdown</List.Item>
                        <List.Item>Кэширование в Redis</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Port: 8000</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="grape" size="lg" radius="md">
                          <IconStack2 size={20} />
                        </ThemeIcon>
                        <Text fw={600}>Sync Service</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Синхронный сервис потоковой обработки. Реализован на Python.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>sherpa-onnx модели</List.Item>
                        <List.Item>Vosk-compatible</List.Item>
                        <List.Item>Endpoint detection</List.Item>
                        <List.Item>Redis distributed locks</List.Item>
                        <List.Item>NATS pub/sub</List.Item>
                        <List.Item>Потоковая обработка</List.Item>
                      </List>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="teal" size="lg" radius="md">
                          <IconCloud size={20} />
                        </ThemeIcon>
                        <Text fw={600}>MinIO</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        S3-совместимое объектное хранилище.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Хранение аудиофайлов</List.Item>
                        <List.Item>Хранение результатов</List.Item>
                        <List.Item>S3 совместимость</List.Item>
                        <List.Item>Web console</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Ports: 9000, 9001</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="orange" size="lg" radius="md">
                          <IconMessage size={20} />
                        </ThemeIcon>
                        <Text fw={600}>NATS JetStream</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Message broker с поддержкой JetStream.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Persistent messages</List.Item>
                        <List.Item>At-least-once</List.Item>
                        <List.Item>Consumer groups</List.Item>
                        <List.Item>Subject-based routing</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Ports: 4222, 8222</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="red" size="lg" radius="md">
                          <IconDatabase size={20} />
                        </ThemeIcon>
                        <Text fw={600}>PostgreSQL</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Реляционная база данных.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Хранение задач</List.Item>
                        <List.Item>Хранение результатов</List.Item>
                        <List.Item>Webhook configs</List.Item>
                        <List.Item>Liquibase миграции</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Port: 5432</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="violet" size="lg" radius="md">
                          <IconKey size={20} />
                        </ThemeIcon>
                        <Text fw={600}>Keycloak</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Identity and Access Management.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>OAuth2/OIDC provider</List.Item>
                        <List.Item>JWT token issuance</List.Item>
                        <List.Item>User management</List.Item>
                        <List.Item>Role-based access</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Port: 8080</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="pink" size="lg" radius="md">
                          <IconClock size={20} />
                        </ThemeIcon>
                        <Text fw={600}>Redis</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        In-memory database и кэш.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Distributed locks</List.Item>
                        <List.Item>Кэширование</List.Item>
                        <List.Item>Идемпотентность</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Port: 6379</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 4 }}>
                  <Card padding="md" radius="md" withBorder h="100%">
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="filled" color="cyan" size="lg" radius="md">
                          <IconDeviceDesktop size={20} />
                        </ThemeIcon>
                        <Text fw={600}>PGAdmin</Text>
                      </Group>
                      <Text size="sm" c="dimmed">
                        Веб-интерфейс для PostgreSQL.
                      </Text>
                      <List spacing={4} size="xs">
                        <List.Item>Управление БД</List.Item>
                        <List.Item>SQL editor</List.Item>
                        <List.Item>Мониторинг</List.Item>
                      </List>
                      <Text size="xs" c="dimmed">Port: 5050</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
              </Grid>
            </Stack>
          </Card>

          {/* NATS Topics */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">NATS Топики и сообщения</Title>
              
              <Grid gap="xl">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Card padding="md" radius="md" withBorder>
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="light" color="blue" size="lg">
                          <IconFileMusic size={18} />
                        </ThemeIcon>
                        <Text fw={600}>Async топики</Text>
                      </Group>
                      <List spacing="xs" size="sm">
                        <List.Item>
                          <Text size="sm"><Code>transcriber.async.request</Code> — запросы на транскрибацию</Text>
                        </List.Item>
                        <List.Item>
                          <Text size="sm"><Code>transcriber.async.response</Code> — результаты обработки</Text>
                        </List.Item>
                      </List>
                      <Text size="sm" c="dimmed">Использует JetStream для персистентности</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Card padding="md" radius="md" withBorder>
                    <Stack gap="sm">
                      <Group>
                        <ThemeIcon variant="light" color="green" size="lg">
                          <IconMicrophone size={18} />
                        </ThemeIcon>
                        <Text fw={600}>Sync топики</Text>
                      </Group>
                      <List spacing="xs" size="sm">
                        <List.Item>
                          <Text size="sm"><Code>transcriber.sync.init</Code> — инициализация сессии</Text>
                        </List.Item>
                        <List.Item>
                          <Text size="sm"><Code>transcriber.sync.processing.*</Code> — аудио-данные</Text>
                        </List.Item>
                        <List.Item>
                          <Text size="sm"><Code>transcriber.sync.response.*</Code> — результаты</Text>
                        </List.Item>
                        <List.Item>
                          <Text size="sm"><Code>transcriber.sync.status.*</Code> — статусы</Text>
                        </List.Item>
                      </List>
                      <Text size="sm" c="dimmed">Core NATS (без JetStream)</Text>
                    </Stack>
                  </Card>
                </Grid.Col>
              </Grid>
            </Stack>
          </Card>

          {/* Data Formats */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">Форматы данных</Title>
              
              <Grid gap="xl">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg">Аудио форматы</Text>
                    <List spacing="xs">
                      <List.Item><Text size="sm"><Code>WAV</Code> — рекомендуемый</Text></List.Item>
                      <List.Item><Text size="sm"><Code>MP3</Code></Text></List.Item>
                      <List.Item><Text size="sm"><Code>FLAC</Code></Text></List.Item>
                      <List.Item><Text size="sm"><Code>OGG</Code></Text></List.Item>
                      <List.Item><Text size="sm"><Code>M4A</Code></Text></List.Item>
                    </List>
                    <Text size="sm" c="dimmed">
                      Рекомендуемые параметры: WAV, 16kHz, mono, float32
                    </Text>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg">Входные данные</Text>
                    <List spacing="xs">
                      <List.Item>Одиночный файл (S3 путь)</List.Item>
                      <List.Item>Архив .zip (до 100 МБ, до 1000 файлов)</List.Item>
                      <List.Item>Список файлов (до 100)</List.Item>
                      <List.Item>Аудиопоток (base64, float32, 16kHz)</List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg">Результат async</Text>
                    <List spacing="xs">
                      <List.Item>Текст сегмента</List.Item>
                      <List.Item>Timestamps (start, end)</List.Item>
                      <List.Item>Токены модели</List.Item>
                      <List.Item>Вероятности (logprob, no_speech)</List.Item>
                      <List.Item>Слова с timestamps</List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg">Результат sync</Text>
                    <List spacing="xs">
                      <List.Item>Распознанный текст</List.Item>
                      <List.Item>Флаг endpoint (конец фразы)</List.Item>
                      <List.Item>Промежуточные результаты</List.Item>
                      <List.Item>Ошибки обработки</List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
              </Grid>
            </Stack>
          </Card>

          {/* Security */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">Безопасность</Title>
              
              <Grid gap="xl">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Group>
                      <ThemeIcon variant="light" color="violet" size="lg">
                        <IconKey size={18} />
                      </ThemeIcon>
                      <Text fw={600} size="lg">Авторизация</Text>
                    </Group>
                    <List spacing="xs">
                      <List.Item>OAuth2/OIDC через Keycloak</List.Item>
                      <List.Item>JWT токены с подписью RS256</List.Item>
                      <List.Item>PKCE для SPA клиентов</List.Item>
                      <List.Item>Роль <Code>transcriber</Code> для доступа к API</List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Group>
                      <ThemeIcon variant="light" color="orange" size="lg">
                        <IconLock size={18} />
                      </ThemeIcon>
                      <Text fw={600} size="lg">Надёжность</Text>
                    </Group>
                    <List spacing="xs">
                      <List.Item>At-least-once доставка (NATS)</List.Item>
                      <List.Item>Redis distributed locks</List.Item>
                      <List.Item>Идемпотентность задач</List.Item>
                      <List.Item>Graceful shutdown</List.Item>
                    </List>
                  </Stack>
                </Grid.Col>
              </Grid>
            </Stack>
          </Card>

          {/* Redis Details */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">Redis - кэширование и блокировки</Title>
              <Text c="dimmed" ta="center">
                Redis используется для распределённых блокировок, кэширования результатов и 
                хранения состояния задач.
              </Text>
              
              <Grid gap="xl">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg" c="blue">Async Service</Text>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">🔒 Distributed Locks (идемпотентность)</Text>
                      <Code block>{"async-jobs:{job_id}"}</Code>
                      <Text size="xs" c="dimmed">
                        Блокировка задачи для предотвращения повторной обработки. 
                        TTL: 60 сек с автоматическим продлением.
                      </Text>
                    </Box>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">📄 Маппинг файлов</Text>
                      <Code block>{"async-jobs:{job_id}:file_map:{file_hash}"}</Code>
                      <Text size="xs" c="dimmed">
                        Хранение соответствия файла task_id в Croc API. 
                        TTL: 600 сек.
                      </Text>
                    </Box>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">📋 Task IDs</Text>
                      <Code block>{"async-jobs:{job_id}:api_tasks"}</Code>
                      <Text size="xs" c="dimmed">
                        SET со всеми task_id для job_id. Позволяет отслеживать 
                        и восстанавливать задачи после сбоев. TTL: 600 сек.
                      </Text>
                    </Box>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">💾 Кэш результатов</Text>
                      <Code block>{"async-jobs:{job_id}"}</Code>
                      <Text size="xs" c="dimmed">
                        Кэширование готового результата транскрибации. 
                        TTL: 7200 сек (2 часа).
                      </Text>
                    </Box>
                  </Stack>
                </Grid.Col>
                
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg" c="green">Sync Service</Text>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">🔒 Блокировка сессии</Text>
                      <Code block>{"transcriber.sync.{job_id}"}</Code>
                      <Text size="xs" c="dimmed">
                        Distributed lock для активной сессии потоковой транскрибации.
                        Non-blocking mode, timeout: 10 сек.
                      </Text>
                    </Box>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">👥 Reader Counters</Text>
                      <Code block>{"{key}:read"}</Code>
                      <Text size="xs" c="dimmed">
                        Счётчики активных читателей для реализации read-write lock.
                        Используется Lua-скрипт для атомарных операций.
                      </Text>
                    </Box>
                    
                    <Box>
                      <Text size="sm" fw={500} mb="xs">🔐 Write Locks</Text>
                      <Code block>{"{key}:write"}</Code>
                      <Text size="xs" c="dimmed">
                        Блокировка записи с проверкой активных читателей.
                        Предотвращает конфликты при параллельных сессиях.
                      </Text>
                    </Box>
                  </Stack>
                </Grid.Col>
              </Grid>
              
              <Box>
                <Text fw={600} mb="xs">Пример workflow async с Redis:</Text>
                <Box p="md" bg="var(--mantine-color-dark-6)" style={{ borderRadius: 8 }}>
                  <Stack gap={4}>
                    <Text size="sm">1. POST <Code>transcriber.async.request</Code> → Gateway</Text>
                    <Text size="sm">2. Async Service: <Code>{"SETNX async-jobs:{job_id}"}</Code> ( acquire lock)</Text>
                    <Text size="sm">3. Обработка аудио, сохранение в <Code>{"async-jobs:{job_id}:file_map:*"}</Code></Text>
                    <Text size="sm">4. Результат: <Code>{"SET async-jobs:{job_id} ... EX 7200"}</Code></Text>
                    <Text size="sm">5. ACK в NATS → <Code>{"DEL async-jobs:{job_id}"}</Code> (release lock)</Text>
                  </Stack>
                </Box>
              </Box>
            </Stack>
          </Card>

          {/* Flow Diagrams */}
          <Card padding="xl" radius="md" withBorder>
            <Stack gap="lg">
              <Title order={2} ta="center">Процесс обработки</Title>
              
              <Grid gap="xl">
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg" ta="center">Async обработка</Text>
                    <Box p="md" bg="var(--mantine-color-dark-6)" style={{ borderRadius: 8 }}>
                      <Stack gap="xs" align="center">
                        <Group gap="xs"><IconApiApp size={16} /><Text size="sm">Клиент (API Gateway)</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconFile size={16} /><Text size="sm">Запрос (NATS)</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconServer size={16} /><Text size="sm">Async Service</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconCloud size={16} /><Text size="sm">MinIO (S3)</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconCheck size={16} /><Text size="sm">Результат → БД</Text></Group>
                      </Stack>
                    </Box>
                  </Stack>
                </Grid.Col>
                <Grid.Col span={{ base: 12, md: 6 }}>
                  <Stack gap="md">
                    <Text fw={600} size="lg" ta="center">Sync обработка</Text>
                    <Box p="md" bg="var(--mantine-color-dark-6)" style={{ borderRadius: 8 }}>
                      <Stack gap="xs" align="center">
                        <Group gap="xs"><IconApiApp size={16} /><Text size="sm">Клиент → Gateway</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconMessage size={16} /><Text size="sm">INIT (NATS)</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconStack2 size={16} /><Text size="sm">Sync Service</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconMicrophone size={16} /><Text size="sm">Аудио чанки</Text></Group>
                        <IconArrowRight size={16} style={{ transform: 'rotate(90deg)' }} />
                        <Group gap="xs"><IconCheck size={16} /><Text size="sm">Результат realtime</Text></Group>
                      </Stack>
                    </Box>
                  </Stack>
                </Grid.Col>
              </Grid>
            </Stack>
          </Card>

          {/* Getting Started */}
          <Card padding="lg" radius="md" withBorder bg="var(--mantine-color-dark-6)">
            <Group justify="space-between" wrap="nowrap">
              <Box>
                <Text fw={600} size="lg">Готовы начать?</Text>
                <Text size="sm" c="dimmed">
                  Войдите в систему для получения доступа к API и документации
                </Text>
              </Box>
              <Button size="md">Документация API</Button>
            </Group>
          </Card>
        </Stack>
      </Container>
    </Box>
  );
}