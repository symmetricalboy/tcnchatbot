import { useEffect, useState } from 'react';
import twa from '@twa-dev/sdk';

function App() {
  const [themeParams] = useState(twa.themeParams);

  useEffect(() => {
    twa.ready();
    twa.expand();
  }, []);

  return (
    <div style={{
      backgroundColor: themeParams.bg_color || '#ffffff',
      color: themeParams.text_color || '#000000',
      minHeight: '100vh',
      padding: '20px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
    }}>
      <h1>TCN Mini App</h1>
      <p>Hello, {twa.initDataUnsafe?.user?.first_name || 'Guest'}!</p>
      <button 
        onClick={() => twa.showAlert('Hello from TCN Mini App!')}
        style={{
          backgroundColor: themeParams.button_color || '#3390ec',
          color: themeParams.button_text_color || '#ffffff',
          border: 'none',
          padding: '10px 20px',
          borderRadius: '8px',
          cursor: 'pointer',
          marginTop: '20px'
        }}
      >
        Show Alert
      </button>
    </div>
  );
}

export default App;
