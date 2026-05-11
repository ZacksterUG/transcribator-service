import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { BrowserRouter } from 'react-router-dom'
import { createTheme, type MantineColorsTuple, MantineProvider } from "@mantine/core";
import { UserProvider } from './context/UserContext';
import '@mantine/core/styles.css';

const colorScheme: MantineColorsTuple = [
    "#ebf9ff",
    "#d6f1fb",
    "#a8e2f9",
    "#79d2f7",
    "#5ac5f6",
    "#4bbdf5",
    "#42b9f6",
    "#36a3dc",
    "#2791c5",
    "#002c3d"
];

const theme = createTheme({
    colors: { colorScheme: colorScheme },
    primaryColor: 'colorScheme',

});

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <BrowserRouter>
            <MantineProvider theme={theme} defaultColorScheme="dark">
                <UserProvider>
                    <div style={{ backgroundColor: colorScheme[9],  minHeight: '100vh' }}>
                        <App />
                    </div>
                </UserProvider>
            </MantineProvider>
        </BrowserRouter>
    </StrictMode>,
)