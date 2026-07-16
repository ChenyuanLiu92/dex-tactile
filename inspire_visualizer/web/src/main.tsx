import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@fontsource/barlow-condensed/latin-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'

import { UnifiedApp } from './UnifiedApp'
import { I18nProvider } from './i18n/I18nProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <I18nProvider><UnifiedApp /></I18nProvider>
  </StrictMode>,
)
