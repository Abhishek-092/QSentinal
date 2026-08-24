import React, { useEffect, useState } from 'react';
import Landing from './components/Landing';
import Console from './components/Console';
import { ThemeProvider } from './ThemeContext';

function viewFromHash() {
  return window.location.hash === '#lab' ? 'console' : 'landing';
}

function AppRoutes() {
  const [view, setView] = useState(viewFromHash);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const enterLab = () => {
    window.location.hash = 'lab';
    setView('console');
    window.scrollTo(0, 0);
  };

  const exitLab = () => {
    window.location.hash = '';
    setView('landing');
    window.scrollTo(0, 0);
  };

  if (view === 'console') {
    return <Console onExit={exitLab} />;
  }
  return <Landing onEnterLab={enterLab} />;
}

export default function App() {
  return (
    <ThemeProvider>
      <AppRoutes />
    </ThemeProvider>
  );
}
