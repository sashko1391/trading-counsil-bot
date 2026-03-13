import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import WarRoom from './WarRoom.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <WarRoom />
  </StrictMode>,
)
