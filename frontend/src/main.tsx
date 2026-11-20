import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

// Safely initialize Telegram WebApp viewport expansion
if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
  try {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  } catch (err) {
    console.warn('Telegram WebApp initialization error:', err);
  }
}

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
