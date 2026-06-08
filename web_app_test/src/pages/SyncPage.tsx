import { useState, useRef, useEffect, useCallback } from 'react';
import { Container, Title, Text, Stack, Card, Group, ThemeIcon, Badge, Button, Box, Alert, Loader } from '@mantine/core';
import { IconMicrophone, IconPlayerStop, IconPlayerPlay, IconWaveSawTool, IconApi } from '@tabler/icons-react';

const WS_BACKEND_URL = import.meta.env.VITE_WS_URL + '/ws/sync';

const SAMPLE_RATE = 16000;
const CHUNK_SIZE = 1024;

type ConnectionStatus = 'disconnected' | 'connecting' | 'ready' | 'recording' | 'finished' | 'error';

export function SyncPage() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);
  const [currentText, setCurrentText] = useState('');
  const [finalSegments, setFinalSegments] = useState<string[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);

  const stopRecording = useCallback(() => {
    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  }, []);

  const connectWebSocket = useCallback(() => {
    return new Promise<void>((resolve, reject) => {
      setStatus('connecting');
      setError(null);

      const wsUrl = WS_BACKEND_URL;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        resolve();
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          console.log('WebSocket message:', msg);

          if (msg.status === 'ready') {
            setStatus('ready');
            return;
          }

          if (msg.type === 'response' && msg.data?.result) {
            const result = msg.data.result;
            if (result.is_endpoint) {
              if (result.text && result.text !== currentText) {
                setFinalSegments(prev => [...prev, result.text]);
              }
              setCurrentText('');
            } else {
              if (result.text !== currentText) {
                setCurrentText(result.text);
              }
            }
          }

          if (msg.type === 'error') {
            setError(msg.error || 'Unknown error');
            setStatus('error');
          }
        } catch (e) {
          console.error('Failed to parse message:', e);
        }
      };

      ws.onerror = (e) => {
        console.error('WebSocket error:', e);
        setError('WebSocket connection error');
        setStatus('error');
        reject(new Error('WebSocket connection error'));
      };

      ws.onclose = (e) => {
        console.log('WebSocket closed:', e.code, e.reason);
        if (status !== 'error' && status !== 'finished') {
          setStatus('disconnected');
        }
      };

      wsRef.current = ws;
    });
  }, [currentText, status]);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      
      const scriptProcessor = audioContext.createScriptProcessor(CHUNK_SIZE, 1, 1);
      scriptProcessorRef.current = scriptProcessor;

      const sendAudioChunk = (inputData: Float32Array) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;
        
        const bytes = inputData.buffer;
        let binary = '';
        const bytesArray = new Uint8Array(bytes);
        for (let i = 0; i < bytesArray.length; i++) {
          binary += String.fromCharCode(bytesArray[i]);
        }
        const base64 = btoa(binary);
        
        wsRef.current.send(JSON.stringify({ bytes: base64 }));
      };

      scriptProcessor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        sendAudioChunk(inputData);
      };

      source.connect(scriptProcessor);
      scriptProcessor.connect(audioContext.destination);

      setStatus('recording');

    } catch (e) {
      console.error('Failed to start recording:', e);
      setError(e instanceof Error ? e.message : 'Failed to access microphone');
      setStatus('error');
    }
  }, []);

  const handleStart = async () => {
    await connectWebSocket();
    await startRecording();
  };

  const handleStop = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ finish: true }));
    }
    
    stopRecording();
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setStatus('finished');
  };

  const handleReset = () => {
    setCurrentText('');
    setFinalSegments([]);
    setError(null);
    setStatus('disconnected');
  };

  useEffect(() => {
    return () => {
      stopRecording();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [stopRecording]);

  const isRecording = status === 'recording';
  const isReady = status === 'ready' || status === 'recording';

  return (
    <Container size="lg" py="xl">
      <Stack gap="xl">
        <Group>
          <ThemeIcon size={48} radius="md" variant="light" color="green">
            <IconMicrophone size={24} />
          </ThemeIcon>
          <Box>
            <Title order={2}>Синхронная обработка</Title>
            <Text c="dimmed">Транскрибация в реальном времени</Text>
          </Box>
        </Group>

        <Card padding="xl" radius="md" withBorder>
          <Stack gap="md">
            <Group justify="space-between">
              <Group gap="sm">
                <IconWaveSawTool size={20} />
                <Text fw={600} size="lg">Микрофонная транскрибация</Text>
              </Group>
              <Badge color={isRecording ? 'red' : isReady ? 'green' : 'gray'}>
                {status}
              </Badge>
            </Group>

            {error && (
              <Alert color="red" title="Ошибка">
                {error}
              </Alert>
            )}

            <Group justify="center" gap="md" py="lg">
              {!isRecording ? (
                <Button
                  size="lg"
                  leftSection={<IconPlayerPlay size={20} />}
                  onClick={handleStart}
                  disabled={status === 'connecting'}
                >
                  {status === 'connecting' ? 'Подключение...' : 'Начать запись'}
                </Button>
              ) : (
                <Button
                  size="lg"
                  color="red"
                  leftSection={<IconPlayerStop size={20} />}
                  onClick={handleStop}
                >
                  Остановить запись
                </Button>
              )}
            </Group>

            {status === 'connecting' && (
              <Group justify="center" gap="xs">
                <Loader size="sm" />
                <Text c="dimmed">Подключение к серверу...</Text>
              </Group>
            )}

            {(isReady || finalSegments.length > 0) && (
              <Box>
                <Text fw={500} mb="xs">Транскрипция:</Text>
                <Stack gap="xs">
                  {finalSegments.map((segment, i) => (
                    <Card key={i} padding="sm" withBorder>
                      <Text>{segment}</Text>
                    </Card>
                  ))}
                  {currentText && (
                    <Card padding="sm" withBorder bg="blue.0">
                      <Text fw={500}>{currentText}</Text>
                      <Badge size="xs" color="blue" mt="xs">Промежуточный результат</Badge>
                    </Card>
                  )}
                </Stack>
              </Box>
            )}

            {(status === 'finished' || status === 'disconnected') && finalSegments.length > 0 && (
              <Button variant="outline" onClick={handleReset}>
                Начать заново
              </Button>
            )}
          </Stack>
        </Card>

        <Card padding="lg" radius="md" withBorder>
          <Group gap="xs" mb="sm">
            <IconApi size={18} />
            <Text fw={500}>Информация о подключении</Text>
          </Group>
          <Stack gap="xs">
            <Text size="sm"><b>WebSocket URL:</b> {WS_BACKEND_URL}</Text>
            <Text size="sm"><b>Аудио формат:</b> 16kHz, mono, float32</Text>
          </Stack>
        </Card>
      </Stack>
    </Container>
  );
}