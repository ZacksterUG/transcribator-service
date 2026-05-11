import { Group, Button, Container, Box, Title, Avatar, Menu, NavLink } from '@mantine/core';
import { IconUser, IconLogout, IconSettings, IconFileMusic, IconMicrophone } from '@tabler/icons-react';
import { useUser } from '../hooks/useUser';
import { useNavigate, Link } from 'react-router-dom';

export function Header() {
  const { user, isAuthenticated, isLoading, logout } = useUser();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const showAuthButtons = !isLoading && isAuthenticated;

  return (
    <Box
      component="header"
      py="md"
      style={{ borderBottom: '1px solid var(--mantine-color-dark-4)' }}
    >
      <Container size="lg">
        <Group justify="space-between">
          <Group gap="md" wrap="nowrap">
            <Title order={3} style={{ cursor: 'pointer' }} onClick={() => navigate('/')}>
              Transcriber
            </Title>
            
            {showAuthButtons && (
              <Group gap={8} wrap="nowrap">
                <NavLink
                  component={Link}
                  to="/async"
                  label="Асинхронная"
                  leftSection={<IconFileMusic size={16} />}
                  variant="light"
                />
                <NavLink
                  component={Link}
                  to="/sync"
                  label="Потоковая"
                  leftSection={<IconMicrophone size={16} />}
                  variant="light"
                />
              </Group>
            )}
          </Group>
          
          {isLoading ? (
            <Box w={100} />
          ) : showAuthButtons ? (
            <Menu shadow="md" width={200}>
              <Menu.Target>
                <Button variant="subtle" leftSection={<Avatar size="sm" radius="xl" />}>
                  {user?.name || user?.email}
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>Аккаунт</Menu.Label>
                <Menu.Item leftSection={<IconSettings size={14} />}>
                  Настройки
                </Menu.Item>
                <Menu.Divider />
                <Menu.Item 
                  leftSection={<IconLogout size={14} />} 
                  color="red"
                  onClick={handleLogout}
                >
                  Выйти
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          ) : (
            <Button
              leftSection={<IconUser size={18} />}
              variant="light"
              color="blue"
              onClick={() => {
                import('../config/keycloak').then(({ login }) => login());
              }}
            >
              Войти
            </Button>
          )}
        </Group>
      </Container>
    </Box>
  );
}