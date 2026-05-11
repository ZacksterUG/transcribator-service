import { Container, Title, Text, Button, Stack, ThemeIcon } from '@mantine/core';
import { IconShieldLock } from '@tabler/icons-react';
import { useNavigate } from 'react-router-dom';

export function ForbiddenPage() {
  const navigate = useNavigate();

  return (
    <Container size="sm" py={100}>
      <Stack align="center" gap="xl">
        <ThemeIcon size={80} radius="md" color="red" variant="light">
          <IconShieldLock size={40} />
        </ThemeIcon>
        <Title order={2} ta="center">Доступ запрещён</Title>
        <Text c="dimmed" ta="center" maw={400}>
          У вас недостаточно прав для просмотра этой страницы.
          Обратитесь к администратору для получения доступа.
        </Text>
        <Button onClick={() => navigate('/')}>Вернуться на главную</Button>
      </Stack>
    </Container>
  );
}