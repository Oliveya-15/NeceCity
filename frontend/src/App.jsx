import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { CityProvider } from './hooks/CityContext'
import CommandCenter from './pages/CommandCenter'
import CityMonitor from './pages/CityMonitor'
import InspectAnalyze from './pages/InspectAnalyze'
import Insights from './pages/Insights'
import ActionCenter from './pages/ActionCenter'
import AdviceCenter from './pages/AdviceCenter'

export default function App() {
  return (
    <CityProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/monitor" element={<CityMonitor />} />
          <Route path="/inspect" element={<InspectAnalyze />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/action-center" element={<ActionCenter />} />
          <Route path="/advice" element={<AdviceCenter />} />
        </Routes>
      </BrowserRouter>
    </CityProvider>
  )
}
