import { useEffect, useRef, useState } from 'react'
import { Check, Cloud, CloudRain, CloudSun, Coffee, Home, ListTodo, Moon, RefreshCw, Settings, Snowflake, Sun, TimerReset, X } from 'lucide-react'
import './App.css'

type Page = 'home' | 'tasks' | 'timer' | 'settings'
type Mood = 'happy' | 'focused' | 'sleepy'
type DeskTask = { id: string; title: string; done: boolean; status?: string; due?: string }
type TimerMode = 'timer' | 'pomodoro'
type TimerPhase = 'work' | 'break'

function BuddyFace({ mood }: { mood: Mood }) {
  return (
    <div className={`buddy buddy-${mood}`} aria-label={`Deskbuddy ist ${mood}`}>
      <svg viewBox="0 0 300 260" role="img">
        <ellipse className="buddy-shadow" cx="150" cy="231" rx="92" ry="14" />
        <path className="buddy-ear left-ear" d="M48 116C25 102 20 70 41 57c18-11 38 5 42 31" />
        <path className="buddy-ear right-ear" d="M252 116c23-14 28-46 7-59-18-11-38 5-42 31" />
        <path className="buddy-body" d="M150 35c68 0 112 45 112 112 0 65-43 89-112 89S38 212 38 147C38 80 82 35 150 35Z" />
        <g className="eyes">
          <ellipse cx="112" cy="132" rx="20" ry="27" />
          <ellipse cx="188" cy="132" rx="20" ry="27" />
        </g>
        {mood === 'happy' && <path className="mouth happy" d="M127 176c12 17 34 17 46 0" />}
        {mood === 'focused' && <><path className="brow left" d="M94 99l36 8" /><path className="brow right" d="M206 99l-36 8" /><path className="mouth" d="M137 184h26" /></>}
        {mood === 'sleepy' && <><path className="mouth sleepy" d="M136 183c9 8 19 8 28 0" /><path className="sleep-z" d="M222 86l13-13m-1 24 16-16" /></>}
      </svg>
    </div>
  )
}

function App() {
  const [page, setPage] = useState<Page>('home')
  const [now, setNow] = useState(new Date())
  const [workMinutes, setWorkMinutes] = useState(() => Number(localStorage.getItem('deskbuddy_work_minutes') || 25))
  const [breakMinutes, setBreakMinutes] = useState(() => Number(localStorage.getItem('deskbuddy_break_minutes') || 5))
  const [timerMode, setTimerMode] = useState<TimerMode>(() => localStorage.getItem('deskbuddy_timer_mode') === 'pomodoro' ? 'pomodoro' : 'timer')
  const [timerPhase, setTimerPhase] = useState<TimerPhase>('work')
  const [pomodoroCount, setPomodoroCount] = useState(0)
  const [secondsLeft, setSecondsLeft] = useState(() => Number(localStorage.getItem('deskbuddy_work_minutes') || 25) * 60)
  const [running, setRunning] = useState(false)
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('deskbuddy_dark') === 'true')
  const [language, setLanguage] = useState(() => localStorage.getItem('deskbuddy_language') || 'Deutsch')
  const [syncMinutes, setSyncMinutes] = useState(() => localStorage.getItem('deskbuddy_sync') || '15')
  const [notionStatus, setNotionStatus] = useState('Nicht konfiguriert')
  const [settingsSaved, setSettingsSaved] = useState(false)
  const [tasks, setTasks] = useState<DeskTask[]>([])
  const [taskFilter, setTaskFilter] = useState<'Alle' | 'Nicht begonnen' | 'Begonnen' | 'Erledigt'>('Nicht begonnen')
  const [quickMenuOpen, setQuickMenuOpen] = useState(false)
  const [brightness, setBrightness] = useState(() => Number(localStorage.getItem('deskbuddy_brightness') || 70))
  const [weather, setWeather] = useState<{ temperature: number | null; condition: string; icon: string; city: string; status: string }>(() => ({ temperature: null, condition: 'Wetter wird geladen', icon: 'unknown', city: '', status: 'loading' }))
  const [weatherApiKey, setWeatherApiKey] = useState('')
  const [weatherCity, setWeatherCity] = useState(() => localStorage.getItem('deskbuddy_weather_city') || 'Berlin')
  const swipeStart = useRef<{ x: number; y: number } | null>(null)

  const loadTasks = () => {
    fetch('/api/tasks')
      .then((response) => response.ok ? response.json() : { items: [] })
      .then((result: { items?: DeskTask[] }) => setTasks(result.items || []))
      .catch(() => setTasks([]))
  }

  useEffect(() => {
    const clock = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(clock)
  }, [])

  const loadWeather = () => {
    fetch('/api/weather')
      .then((response) => response.ok ? response.json() : { status: 'error', temperature: null, condition: 'Wetter nicht erreichbar', icon: 'unknown', city: weatherCity })
      .then((result) => setWeather(result))
      .catch(() => setWeather({ temperature: null, condition: 'Wetter nicht erreichbar', icon: 'unknown', city: weatherCity, status: 'error' }))
  }

  useEffect(() => {
    loadTasks()
    loadWeather()
    const weatherRefresh = window.setInterval(loadWeather, 30 * 60 * 1000)

    fetch('/api/settings')
      .then((response) => response.ok ? response.json() : {})
      .then((settings: Record<string, string>) => {
        if (settings.darkMode !== undefined) setDarkMode(settings.darkMode === 'true')
        if (settings.language) setLanguage(settings.language)
        if (settings.syncMinutes) setSyncMinutes(settings.syncMinutes)
        if (settings.weatherCity) {
          setWeatherCity(settings.weatherCity)
          localStorage.setItem('deskbuddy_weather_city', settings.weatherCity)
        }
        if (settings.timerMode === 'timer' || settings.timerMode === 'pomodoro') {
          setTimerMode(settings.timerMode)
          localStorage.setItem('deskbuddy_timer_mode', settings.timerMode)
        }
        if (settings.breakMinutes) {
          const minutes = Math.max(1, Math.min(60, Number(settings.breakMinutes)))
          setBreakMinutes(minutes)
          localStorage.setItem('deskbuddy_break_minutes', String(minutes))
        }
        if (settings.workMinutes) {
          const minutes = Math.max(1, Math.min(120, Number(settings.workMinutes)))
          setWorkMinutes(minutes)
          if (!running) setSecondsLeft(minutes * 60)
          localStorage.setItem('deskbuddy_work_minutes', String(minutes))
        }
      })
      .catch(() => undefined)

    fetch('/api/system/brightness')
      .then((response) => response.ok ? response.json() : { brightness })
      .then((result: { brightness?: number }) => {
        if (typeof result.brightness === 'number') {
          setBrightness(result.brightness)
          localStorage.setItem('deskbuddy_brightness', String(result.brightness))
        }
      })
      .catch(() => undefined)

    fetch('/api/notion/test')
      .then((response) => response.json())
      .then((result) => setNotionStatus(result.status === 'ok' ? 'Verbunden' : 'Nicht konfiguriert'))
      .catch(() => setNotionStatus('Nicht erreichbar'))

    return () => window.clearInterval(weatherRefresh)
  }, [])

  useEffect(() => {
    localStorage.setItem('deskbuddy_dark', String(darkMode))
  }, [darkMode])

  useEffect(() => {
    let touchStart: { x: number; y: number } | null = null

    const onTouchStart = (event: TouchEvent) => {
      const touch = event.changedTouches[0]
      touchStart = touch ? { x: touch.clientX, y: touch.clientY } : null
    }

    const onTouchEnd = (event: TouchEvent) => {
      if (!touchStart) return
      const touch = event.changedTouches[0]
      if (!touch) return
      const dy = touch.clientY - touchStart.y
      const dx = Math.abs(touch.clientX - touchStart.x)

      if (dx < 100 && dy > 35 && touchStart.y < 100) setQuickMenuOpen(true)
      if (dx < 100 && dy < -35 && quickMenuOpen) setQuickMenuOpen(false)
      touchStart = null
    }

    window.addEventListener('touchstart', onTouchStart, { passive: true })
    window.addEventListener('touchend', onTouchEnd, { passive: true })
    return () => {
      window.removeEventListener('touchstart', onTouchStart)
      window.removeEventListener('touchend', onTouchEnd)
    }
  }, [quickMenuOpen])

  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setSecondsLeft((value) => {
      if (value > 1) return value - 1
      if (timerMode === 'pomodoro') {
        setRunning(false)
        if (timerPhase === 'work') {
          setPomodoroCount((count) => {
            const nextCount = count + 1
            setTimerPhase('break')
            setSecondsLeft(nextCount % 4 === 0 ? 15 * 60 : breakMinutes * 60)
            return nextCount
          })
        } else {
          setTimerPhase('work')
          setSecondsLeft(workMinutes * 60)
        }
        return 0
      }
      setRunning(false)
      return 0
    }), 1000)
    return () => window.clearInterval(timer)
  }, [running, timerMode, timerPhase, workMinutes, breakMinutes])

  const mood: Mood = running ? 'focused' : secondsLeft === 0 ? 'sleepy' : 'happy'
  const time = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  const date = now.toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: 'long' })
  const timer = `${Math.floor(secondsLeft / 60).toString().padStart(2, '0')}:${(secondsLeft % 60).toString().padStart(2, '0')}`
  const todayLocal = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const todayTasks = tasks.filter((task) => task.due?.slice(0, 10) === todayLocal)
  const getTaskStatus = (task: DeskTask): 'Nicht begonnen' | 'Begonnen' | 'Erledigt' => task.status === 'Begonnen' || task.status === 'Erledigt' ? task.status : 'Nicht begonnen'

  const setTaskStatus = async (id: string, status: 'Nicht begonnen' | 'Begonnen' | 'Erledigt') => {
    setTasks((items) => items.map((item) => item.id === id ? { ...item, status, done: status === 'Erledigt' } : item))
    await fetch(`/api/tasks/${encodeURIComponent(id)}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    }).catch(() => undefined)
  }

  const saveSetting = async (key: string, value: string) => {
    try {
      await fetch(`/api/settings/${encodeURIComponent(key)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      })
      setSettingsSaved(true)
      window.setTimeout(() => setSettingsSaved(false), 1600)
    } catch {
      setSettingsSaved(false)
    }
  }

  const changeBrightness = (value: number) => {
    setBrightness(value)
    localStorage.setItem('deskbuddy_brightness', String(value))
  }

  const changeWorkMinutes = (value: number) => {
    const minutes = Math.max(1, Math.min(120, value))
    setWorkMinutes(minutes)
    setRunning(false)
    setTimerPhase('work')
    setSecondsLeft(minutes * 60)
    localStorage.setItem('deskbuddy_work_minutes', String(minutes))
    void saveSetting('workMinutes', String(minutes))
  }

  const changeBreakMinutes = (value: number) => {
    const minutes = Math.max(1, Math.min(60, value))
    setBreakMinutes(minutes)
    setRunning(false)
    localStorage.setItem('deskbuddy_break_minutes', String(minutes))
    void saveSetting('breakMinutes', String(minutes))
  }

  const chooseTimerMode = (mode: TimerMode) => {
    setTimerMode(mode)
    setRunning(false)
    setTimerPhase('work')
    setPomodoroCount(0)
    setSecondsLeft(mode === 'pomodoro' ? workMinutes * 60 : workMinutes * 60)
    localStorage.setItem('deskbuddy_timer_mode', mode)
    void saveSetting('timerMode', mode)
  }

  const saveBrightness = async () => {
    await fetch('/api/system/brightness', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brightness }),
    }).catch(() => undefined)
  }

  const WeatherIcon = () => {
    if (weather.icon.startsWith('01')) return <Sun size={21} />
    if (weather.icon.startsWith('09') || weather.icon.startsWith('10') || weather.icon.startsWith('11')) return <CloudRain size={21} />
    if (weather.icon.startsWith('13')) return <Snowflake size={21} />
    if (weather.icon.startsWith('02') || weather.icon.startsWith('03') || weather.icon.startsWith('04')) return <CloudSun size={21} />
    return <Cloud size={21} />
  }

  const saveWeather = async () => {
    const city = weatherCity.trim()
    if (!city) return
    localStorage.setItem('deskbuddy_weather_city', city)
    await fetch('/api/weather/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ apiKey: weatherApiKey, city }),
    }).then((response) => response.ok ? response.json() : null).then(() => {
      setWeatherApiKey('')
      setSettingsSaved(true)
      window.setTimeout(() => setSettingsSaved(false), 1600)
      loadWeather()
    }).catch(() => setSettingsSaved(false))
  }

  const testNotion = async () => {
    setNotionStatus('Wird geprüft…')
    try {
      const response = await fetch('/api/notion/test')
      const result = await response.json()
      setNotionStatus(result.status === 'ok' ? 'Verbunden' : 'Nicht konfiguriert')
    } catch {
      setNotionStatus('Nicht erreichbar')
    }
  }

  return (
    <main
      className={`app-shell${darkMode ? ' dark' : ''}`}
      onPointerDown={(event) => { swipeStart.current = { x: event.clientX, y: event.clientY } }}
      onPointerUp={(event) => {
        if (!swipeStart.current) return
        const dy = event.clientY - swipeStart.current.y
        const dx = Math.abs(event.clientX - swipeStart.current.x)
        if (dx < 100 && dy > 35 && swipeStart.current.y < 100) setQuickMenuOpen(true)
        if (dx < 100 && dy < -35) setQuickMenuOpen(false)
        swipeStart.current = null
      }}
    >
      <button className="quick-menu-peek" aria-label="Schnellmenü öffnen" onClick={() => setQuickMenuOpen(true)}><span /></button>
      <section className="main-panel">
        {page === 'home' && <>
          <header className="topbar">
            <div className="brand"><span className="brand-dot" />deskbuddy</div>
            <div className="weather"><WeatherIcon /><span>{weather.temperature === null ? '—°' : `${weather.temperature}°`}</span><small>{weather.status === 'offline' ? 'Offline · ' : ''}{weather.condition}</small></div>
          </header>
          <div className="home-grid">
            <section className="face-zone">
              <BuddyFace mood={mood} />
              <button className="mood-chip" onClick={() => setPage('settings')}>Guten Nachmittag <span>·</span></button>
            </section>
            <section className="info-zone">
              <div className="clock"><strong>{time}</strong><span>{date}</span></div>
              <button className="pomodoro-card" onClick={() => setPage('timer')}>
                <div className="timer-ring"><TimerReset size={19} /></div>
                <div><small>{running ? 'Fokusphase' : 'Pomodoro'}</small><b>{timer}</b></div>
                <span className="card-arrow">›</span>
              </button>
              <div className="task-card">
                <div className="task-heading"><span>Heute</span><b>{todayTasks.filter((task) => !task.done).length} offen</b></div>
                {todayTasks.filter((task) => !task.done).slice(0, 2).map((task) => (
                  <button className="task-row" key={task.id} onClick={() => setTaskStatus(task.id, 'Erledigt')}>
                    <span className={task.done ? 'check done' : 'check'}>{task.done && <Check size={12} />}</span>
                    <span className={task.done ? 'task-done task-title-home' : 'task-title-home'}>{task.title}</span>
                    <span className={`task-status-badge status-${getTaskStatus(task).replaceAll(' ', '-').toLowerCase()}`}>{getTaskStatus(task)}</span>
                  </button>
                ))}
              </div>
            </section>
          </div>
        </>}

        {page === 'tasks' && <section className="page-view tasks-page">
          <div className="tasks-heading"><div><h1>Aufgaben</h1><p className="eyebrow">Heute · {date}</p></div><button className="refresh-button" onClick={loadTasks}>Aktualisieren</button></div>
          <div className="task-filters" aria-label="Aufgaben filtern">
            {(['Alle', 'Nicht begonnen', 'Begonnen', 'Erledigt'] as const).map((filter) => <button key={filter} className={taskFilter === filter ? 'active' : ''} onClick={() => setTaskFilter(filter)}>{filter}</button>)}
          </div>
          <div className="task-list">
            {todayTasks.filter((task) => taskFilter === 'Alle' || getTaskStatus(task) === taskFilter).map((task) => (
              <div className="full-task" key={task.id}>
                <button className="task-check" onClick={() => setTaskStatus(task.id, task.done ? 'Nicht begonnen' : 'Erledigt')}><span className={task.done ? 'check done' : 'check'}>{task.done && <Check size={14} />}</span></button>
                <div className="task-title"><span className={task.done ? 'task-done' : ''}>{task.title}</span>{task.due && <small>{task.due}</small>}</div>
                <select className={`status-select status-${getTaskStatus(task).replaceAll(' ', '-').toLowerCase()}`} value={getTaskStatus(task)} onChange={(event) => setTaskStatus(task.id, event.target.value as 'Nicht begonnen' | 'Begonnen' | 'Erledigt')}>
                  <option>Nicht begonnen</option><option>Begonnen</option><option>Erledigt</option>
                </select>
              </div>
            ))}
            {todayTasks.filter((task) => taskFilter === 'Alle' || getTaskStatus(task) === taskFilter).length === 0 && <div className="empty-state">Keine Aufgaben in diesem Filter.</div>}
          </div>
        </section>}

        {page === 'timer' && <section className="timer-view">
          <div>
            <div className="timer-mode-switch"><button className={timerMode === 'timer' ? 'active' : ''} onClick={() => chooseTimerMode('timer')}>Normaler Timer</button><button className={timerMode === 'pomodoro' ? 'active' : ''} onClick={() => chooseTimerMode('pomodoro')}>Pomodoro</button></div>
            <small>{timerMode === 'pomodoro' ? timerPhase === 'work' ? 'ARBEITSPHASE' : 'PAUSE' : 'TIMER'}</small>
            <strong>{timer}</strong>
            {timerMode === 'timer' ? <div className="timer-adjust"><button aria-label="Eine Minute abziehen" onClick={() => changeWorkMinutes(workMinutes - 1)}>−</button><span>{workMinutes} Minuten</span><button aria-label="Eine Minute hinzufügen" onClick={() => changeWorkMinutes(workMinutes + 1)}>+</button></div> : <div className="pomodoro-meta"><span>{pomodoroCount % 4}/4 Durchgänge</span><b>{timerPhase === 'work' ? workMinutes : breakMinutes} Min.</b></div>}
          </div>
          <BuddyFace mood={mood} />
          <div className="timer-actions"><button onClick={() => setRunning((value) => !value)}>{running ? 'Pause' : secondsLeft === 0 ? 'Neu starten' : 'Start'}</button><button className="round-action" onClick={() => { setRunning(false); setTimerPhase('work'); setSecondsLeft(workMinutes * 60) }}><TimerReset size={22} /></button></div>
        </section>}

        {page === 'settings' && <section className="page-view settings">
          <div className="settings-heading"><h1>Einstellungen</h1>{settingsSaved && <span className="saved">Gespeichert</span>}</div>
          <button className="setting-row" onClick={() => { const next = !darkMode; setDarkMode(next); void saveSetting('darkMode', String(next)) }}>
            <span>Dark Mode</span><span className={`switch${darkMode ? ' on' : ''}`}><i /></span>
          </button>
          <button className="setting-row" onClick={testNotion}>
            <span><b>Notion</b><small>{notionStatus}</small></span><span className="setting-action">Verbindung testen ›</span>
          </button>
          <button className="setting-row" onClick={() => { const next = language === 'Deutsch' ? 'English' : 'Deutsch'; setLanguage(next); localStorage.setItem('deskbuddy_language', next); void saveSetting('language', next) }}>
            <span><b>Sprache</b><small>Anzeige der Oberfläche</small></span><span className="setting-action">{language} ›</span>
          </button>
          <label className="setting-row timer-mode-setting">
            <span><b>Timer-Modus</b><small>Normaler Countdown oder Pomodoro</small></span>
            <select value={timerMode} onChange={(event) => chooseTimerMode(event.target.value as TimerMode)}>
              <option value="timer">Normaler Timer</option><option value="pomodoro">Pomodoro</option>
            </select>
          </label>
          <div className="setting-row timer-setting">
            <span><b>Arbeitsdauer</b><small>Timer oder Pomodoro-Arbeitsphase</small></span>
            <div className="timer-stepper">
              <button aria-label="Timerdauer verringern" onClick={() => changeWorkMinutes(workMinutes - 1)}>−</button>
              <b>{workMinutes} Min.</b>
              <button aria-label="Timerdauer erhöhen" onClick={() => changeWorkMinutes(workMinutes + 1)}>+</button>
            </div>
          </div>
          {timerMode === 'pomodoro' && <div className="setting-row timer-setting">
            <span><b>Pausendauer</b><small>Kurze Pomodoro-Pause</small></span>
            <div className="timer-stepper">
              <button aria-label="Pausendauer verringern" onClick={() => changeBreakMinutes(breakMinutes - 1)}>−</button>
              <b>{breakMinutes} Min.</b>
              <button aria-label="Pausendauer erhöhen" onClick={() => changeBreakMinutes(breakMinutes + 1)}>+</button>
            </div>
          </div>}
          <div className="setting-row weather-setting">
            <span><b>Wetter</b><small>OpenWeather Ort und API-Key</small></span>
            <div className="weather-config">
              <input aria-label="Wetterort" value={weatherCity} onChange={(event) => setWeatherCity(event.target.value)} />
              <input aria-label="OpenWeather API-Key" type="password" placeholder="API-Key" value={weatherApiKey} onChange={(event) => setWeatherApiKey(event.target.value)} />
              <button onClick={saveWeather}>Speichern</button>
            </div>
          </div>
          <label className="setting-row sync-row">
            <span><b>Synchronisierung</b><small>Notion-Aktualisierung</small></span>
            <select value={syncMinutes} onChange={(event) => { setSyncMinutes(event.target.value); localStorage.setItem('deskbuddy_sync', event.target.value); void saveSetting('syncMinutes', event.target.value) }}>
              <option value="5">Alle 5 Min.</option><option value="15">Alle 15 Min.</option><option value="30">Alle 30 Min.</option>
            </select>
          </label>
        </section>}
      </section>

      {quickMenuOpen && <>
        <button className="quick-backdrop" aria-label="Schnellmenü schließen" onClick={() => setQuickMenuOpen(false)} />
        <section className="quick-menu" aria-label="Schnellmenü">
          <div className="quick-menu-header">
            <div><Sun size={18} /><span>Schnellmenü</span></div>
            <button className="quick-close" aria-label="Schließen" onClick={() => setQuickMenuOpen(false)}><X size={18} /></button>
          </div>
          <label className="brightness-control">
            <div><Sun size={19} /><span>Helligkeit</span><b>{brightness}%</b></div>
            <input
              type="range"
              min="1"
              max="100"
              value={brightness}
              onChange={(event) => changeBrightness(Number(event.target.value))}
              onPointerUp={saveBrightness}
              onKeyUp={saveBrightness}
            />
          </label>
          <div className="quick-actions">
            <button onClick={() => { const next = !darkMode; setDarkMode(next); void saveSetting('darkMode', String(next)) }}>
              <Moon size={20} /><span>{darkMode ? 'Hellmodus' : 'Dark Mode'}</span>
            </button>
            <button onClick={() => { setRunning((value) => !value); setQuickMenuOpen(false) }}>
              <TimerReset size={20} /><span>{running ? 'Timer pausieren' : 'Timer starten'}</span>
            </button>
            <button onClick={() => { loadTasks(); setQuickMenuOpen(false) }}>
              <RefreshCw size={20} /><span>Aktualisieren</span>
            </button>
            <button onClick={() => { setPage('settings'); setQuickMenuOpen(false) }}>
              <Settings size={20} /><span>Einstellungen</span>
            </button>
          </div>
        </section>
      </>}

      <nav className="nav-bar" aria-label="Hauptnavigation">
        <button className={page === 'home' ? 'active' : ''} onClick={() => setPage('home')}><Home size={21} /><span>Home</span></button>
        <button className={page === 'tasks' ? 'active' : ''} onClick={() => setPage('tasks')}><ListTodo size={21} /><span>Aufgaben</span></button>
        <button className={page === 'timer' ? 'active' : ''} onClick={() => setPage('timer')}><Coffee size={21} /><span>Timer</span></button>
        <button className={page === 'settings' ? 'active' : ''} onClick={() => setPage('settings')}><Settings size={21} /><span>Optionen</span></button>
      </nav>
    </main>
  )
}

export default App
