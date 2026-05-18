import { Routes, Route } from 'react-router-dom'
import { PatientsPage } from './pages/PatientsPage'
import { PatientPage } from './pages/PatientPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<PatientsPage />} />
      <Route path="/patient/:id" element={<PatientPage />} />
    </Routes>
  )
}

export default App
