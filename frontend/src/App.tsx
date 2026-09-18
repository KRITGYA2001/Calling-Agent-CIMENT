import { useEffect, useState } from 'react'

type HealthStatus = 'checking' | 'ok' | 'error'

function App() {
  const [status, setStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? setStatus('ok') : setStatus('error')))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-semibold">CIMET Hackathon</h1>
      <p className="text-neutral-400">
        Scaffold ready. Backend status:{' '}
        <span
          className={
            status === 'ok'
              ? 'text-green-400'
              : status === 'error'
                ? 'text-red-400'
                : 'text-yellow-400'
          }
        >
          {status}
        </span>
      </p>
      <p className="text-neutral-500 text-sm max-w-md text-center">
        Start the backend (`uvicorn app.main:app --reload` from{' '}
        <code>backend/</code>) to see this turn green.
      </p>
    </div>
  )
}

export default App
