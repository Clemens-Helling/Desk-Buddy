import { useEffect, useRef, useState } from 'react'
import { CalendarDays, Check, Cloud, CloudRain, CloudSun, Coffee, Home, ListTodo, Moon, Power, RefreshCw, Snowflake, Sun, TimerReset, X } from 'lucide-react'
import './App.css'

type Page = 'home' | 'tasks' | 'calendar' | 'timer' | 'config'
type Mood = 'neutral' | 'happy' | 'focused' | 'proud' | 'sleepy' | 'thinking' | 'surprised'
type MoodColor = 'default' | 'focus' | 'success' | 'warning'
type AvatarReaction = { expression: Mood; moodColor: MoodColor; badge: string; message: string }
type DeskTask = { id: string; title: string; done: boolean; status?: string; due?: string }
type CalendarItem = { title: string; start: string; end?: string; location?: string; all_day?: boolean; calendarName?: string }
type IcloudCalendar = { name: string; url: string }
type TimerMode = 'timer' | 'pomodoro'
type TimerPhase = 'work' | 'break'

function BuddyFace({ mood, onClick }: { mood: Mood; onClick?: () => void }) {
  return (
    <button type="button" className={`buddy buddy-${mood}`} aria-label={`Deskbuddy ist ${mood}. Avatar anklicken`} onClick={onClick}>
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
        {mood === 'proud' && <path className="mouth happy" d="M127 176c12 17 34 17 46 0" />}
        {mood === 'thinking' && <><path className="brow left" d="M98 100l30 8" /><path className="brow right" d="M202 100l-30 8" /><path className="mouth" d="M137 184h26" /></>}
        {mood === 'surprised' && <><ellipse className="surprised-mouth" cx="150" cy="181" rx="12" ry="16" /><path className="brow left" d="M94 96l36 5" /><path className="brow right" d="M206 96l-36 5" /></>}
        {mood === 'neutral' && <path className="mouth" d="M137 184h26" />}
      </svg>
    </button>
  )
}

function App() {
  const standaloneConfig = window.location.pathname === '/config'
  const [page, setPage] = useState<Page>(standaloneConfig ? 'config' : 'home')
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
  const [avatarReaction, setAvatarReaction] = useState<AvatarReaction>({ expression: 'happy', moodColor: 'default', badge: 'Bereit', message: 'Guten Tag!' })
  const avatarStarted = useRef(false)
  const [weatherCity, setWeatherCity] = useState(() => localStorage.getItem('deskbuddy_weather_city') || 'Berlin')
  const [calendarItems, setCalendarItems] = useState<CalendarItem[]>([])
  const [calendarStatus, setCalendarStatus] = useState('Nicht konfiguriert')
  const [calendarRefreshing, setCalendarRefreshing] = useState(false)
  const [icloudCalendars, setIcloudCalendars] = useState<IcloudCalendar[]>([])
  const [icloudUsername, setIcloudUsername] = useState('')
  const [icloudPassword, setIcloudPassword] = useState('')
  const [icloudCalendarUrls, setIcloudCalendarUrls] = useState<string[]>([])
  const [nightEnabled, setNightEnabled] = useState(false)
  const [nightStart, setNightStart] = useState('22:00')
  const [nightEnd, setNightEnd] = useState('07:00')
  const [displayAsleep, setDisplayAsleep] = useState(false)
  const [manualDisplaySleep, setManualDisplaySleep] = useState(false)
  const swipeStart = useRef<{ x: number; y: number } | null>(null)

  const loadTasks = () => {
    fetch('/api/tasks')
      .then((response) => response.ok ? response.json() : { items: [] })
      .then((result: { items?: DeskTask[] }) => setTasks(result.items || []))
      .catch(() => setTasks([]))
  }

  const loadCalendar = (showRefreshing = true) => {
    if (showRefreshing) {
      setCalendarRefreshing(true)
      setCalendarStatus('Wird aktualisiert…')
    }
    fetch('/api/calendar', { cache: 'no-store' })
      .then((response) => response.ok ? response.json() : null)
      .then((result: { items?: CalendarItem[]; configured?: boolean; offline?: boolean } | null) => {
        setCalendarItems(result?.items || [])
        if (!result?.configured) setCalendarStatus('Nicht konfiguriert')
        else if (result.offline) setCalendarStatus('Offline · Cache')
        else setCalendarStatus('Synchronisiert')
      })
      .catch(() => setCalendarStatus('Nicht erreichbar'))
      .finally(() => setCalendarRefreshing(false))
  }

  const loadIcloudCalendars = () => {
    fetch('/api/calendar/calendars')
      .then((response) => response.ok ? response.json() : null)
      .then((result: { items?: IcloudCalendar[]; configured?: boolean; error?: string } | null) => {
        setIcloudCalendars(result?.items || [])
        if (!result?.configured) setCalendarStatus('Nicht konfiguriert')
        else if (result.error) setCalendarStatus(result.error)
      })
      .catch(() => setCalendarStatus('Nicht erreichbar'))
  }

  useEffect(() => {
    const clock = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(clock)
  }, [])

  useEffect(() => {
    if (standaloneConfig || manualDisplaySleep) return

    if (!nightEnabled) {
      if (displayAsleep) {
        setDisplayAsleep(false)
        void fetch('/api/system/display', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: true }),
        }).catch(() => undefined)
      }
      return
    }

    const toMinutes = (value: string) => {
      const [hours, minutes] = value.split(':').map(Number)
      return hours * 60 + minutes
    }
    const current = now.getHours() * 60 + now.getMinutes()
    const start = toMinutes(nightStart)
    const end = toMinutes(nightEnd)
    const shouldSleep = start <= end
      ? current >= start && current < end
      : current >= start || current < end

    if (shouldSleep && !displayAsleep) {
      setDisplayAsleep(true)
      void fetch('/api/system/display', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: false }),
      }).catch(() => undefined)
    } else if (!shouldSleep && displayAsleep) {
      setDisplayAsleep(false)
      void fetch('/api/system/display', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true }),
      }).catch(() => undefined)
    }
  }, [now, nightEnabled, nightStart, nightEnd, displayAsleep, manualDisplaySleep, standaloneConfig])

  const triggerAvatar = (event: string, context = '') => {
    setAvatarReaction((current) => ({ ...current, expression: 'thinking' }))
    void fetch('/api/avatar/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, context }),
    })
      .then((response) => response.ok ? response.json() : null)
      .then((reaction: AvatarReaction | null) => {
        if (reaction?.expression) setAvatarReaction(reaction)
      })
      .catch(() => setAvatarReaction({ expression: 'neutral', moodColor: 'default', badge: 'Offline', message: 'Ich bleibe bei dir.' }))
  }

  const loadWeather = () => {
    fetch('/api/weather')
      .then((response) => response.ok ? response.json() : { status: 'error', temperature: null, condition: 'Wetter nicht erreichbar', icon: 'unknown', city: weatherCity })
      .then((result) => setWeather(result))
      .catch(() => setWeather({ temperature: null, condition: 'Wetter nicht erreichbar', icon: 'unknown', city: weatherCity, status: 'error' }))
  }

  useEffect(() => {
    if (!standaloneConfig && !avatarStarted.current) {
      avatarStarted.current = true
      triggerAvatar('app_started', 'Desk Buddy wurde gestartet')
    }
    loadTasks()
    loadWeather()
    loadCalendar()
    loadIcloudCalendars()
    const weatherRefresh = window.setInterval(loadWeather, 30 * 60 * 1000)
    const calendarRefresh = window.setInterval(() => loadCalendar(false), 15 * 60 * 1000)

    fetch('/api/settings')
      .then((response) => response.ok ? response.json() : {})
      .then((settings: Record<string, string>) => {
        if (settings.darkMode !== undefined) setDarkMode(settings.darkMode === 'true')
        if (settings.language) setLanguage(settings.language)
        if (settings.syncMinutes) setSyncMinutes(settings.syncMinutes)
        if (settings.nightEnabled !== undefined) setNightEnabled(settings.nightEnabled === 'true')
        if (settings.nightStart) setNightStart(settings.nightStart)
        if (settings.nightEnd) setNightEnd(settings.nightEnd)
        if (settings.icloudUsername) {
          setIcloudUsername(settings.icloudUsername)
          window.setTimeout(loadIcloudCalendars, 0)
        }
        if (settings.icloudCalendarUrls) {
          try { setIcloudCalendarUrls(JSON.parse(settings.icloudCalendarUrls)) } catch { setIcloudCalendarUrls([]) }
        } else if (settings.icloudCalendarUrl) setIcloudCalendarUrls([settings.icloudCalendarUrl])
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

    return () => {
      window.clearInterval(weatherRefresh)
      window.clearInterval(calendarRefresh)
    }
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
        triggerAvatar('timer_completed', timerMode === 'pomodoro' ? 'Pomodoro-Arbeitsphase beendet' : 'Timer abgelaufen')
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

  const mood: Mood = avatarReaction.expression
  const time = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })
  const date = now.toLocaleDateString('de-DE', { weekday: 'long', day: '2-digit', month: 'long' })
  const timer = `${Math.floor(secondsLeft / 60).toString().padStart(2, '0')}:${(secondsLeft % 60).toString().padStart(2, '0')}`
  const todayLocal = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  const todayTasks = tasks.filter((task) => task.due?.slice(0, 10) === todayLocal)
  const nextCalendarItem = [...calendarItems]
    .filter((item) => {
      if (item.all_day) return item.start.slice(0, 10) >= todayLocal
      const start = new Date(item.start)
      return !Number.isNaN(start.getTime()) && start >= now
    })
    .sort((a, b) => a.start.localeCompare(b.start))[0]
  const calendarDays = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(now)
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() + index)
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    return { date, key, items: calendarItems.filter((item) => item.start.slice(0, 10) === key).sort((a, b) => a.start.localeCompare(b.start)) }
  })
  const getTaskStatus = (task: DeskTask): 'Nicht begonnen' | 'Begonnen' | 'Erledigt' => task.status === 'Begonnen' || task.status === 'Erledigt' ? task.status : 'Nicht begonnen'

  const setTaskStatus = async (id: string, status: 'Nicht begonnen' | 'Begonnen' | 'Erledigt') => {
    setTasks((items) => items.map((item) => item.id === id ? { ...item, status, done: status === 'Erledigt' } : item))
    if (status === 'Erledigt') {
      const task = tasks.find((item) => item.id === id)
      triggerAvatar('task_completed', task?.title ? `Aufgabe erledigt: ${task.title}` : 'Aufgabe erledigt')
    }
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

  const sleepDisplay = async () => {
    setManualDisplaySleep(true)
    setDisplayAsleep(true)
    setQuickMenuOpen(false)
    await fetch('/api/system/display', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: false }),
    }).catch(() => undefined)
  }

  const wakeDisplay = async () => {
    if (!displayAsleep) return
    setManualDisplaySleep(false)
    setDisplayAsleep(false)
    await fetch('/api/system/display', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: true }),
    }).catch(() => undefined)
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

  const saveIcloudCalendar = async () => {
    await fetch('/api/calendar/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: icloudUsername,
        password: icloudPassword,
        calendarUrls: icloudCalendarUrls,
      }),
    }).then((response) => response.ok ? response.json() : null).then(() => {
      setIcloudPassword('')
      setSettingsSaved(true)
      window.setTimeout(() => setSettingsSaved(false), 1600)
      window.setTimeout(loadIcloudCalendars, 50)
      window.setTimeout(loadCalendar, 100)
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
      className={`app-shell${darkMode ? ' dark' : ''}${standaloneConfig ? ' standalone-config' : ''}`}
      onPointerDown={(event) => {
        if (displayAsleep) void wakeDisplay()
        swipeStart.current = { x: event.clientX, y: event.clientY }
      }}
      onPointerUp={(event) => {
        if (!swipeStart.current) return
        const dy = event.clientY - swipeStart.current.y
        const dx = Math.abs(event.clientX - swipeStart.current.x)
        if (dx < 100 && dy > 35 && swipeStart.current.y < 100) setQuickMenuOpen(true)
        if (dx < 100 && dy < -35) setQuickMenuOpen(false)
        swipeStart.current = null
      }}
    >
      {displayAsleep && <button className="display-wake" aria-label="Display einschalten" onClick={wakeDisplay}><span>Display einschalten</span></button>}
      <button className="quick-menu-peek" aria-label="Schnellmenü öffnen" onClick={() => setQuickMenuOpen(true)}><span /></button>
      <section className="main-panel">
        {page === 'home' && <>
          <header className="topbar">
            <div className="brand"><span className="brand-dot" />deskbuddy</div>
            <div className="topbar-status">
              {nextCalendarItem && <button className="next-event" onClick={() => setPage('calendar')}>
                <small>{nextCalendarItem.all_day ? 'Ganztägig' : new Date(nextCalendarItem.start).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}</small>
                <span>{nextCalendarItem.title}</span>
              </button>}
              <div className="weather"><WeatherIcon /><span>{weather.temperature === null ? '—°' : `${weather.temperature}°`}</span><small>{weather.status === 'offline' ? 'Offline · ' : ''}{weather.condition}</small></div>
            </div>
          </header>
          <div className="home-grid">
            <section className="face-zone">
              <BuddyFace mood={mood} onClick={() => triggerAvatar('user_clicked_avatar', 'Der Benutzer hat den Avatar berührt')} />
              <button className={`mood-chip color-${avatarReaction.moodColor}`} onClick={() => triggerAvatar('user_clicked_avatar', 'Der Benutzer hat die Avatar-Nachricht berührt')}><b>{avatarReaction.badge}</b> <span>·</span> {avatarReaction.message}</button>
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

        {page === 'calendar' && <section className="page-view calendar-page">
          <div className="calendar-page-heading">
            <div><h1>Kalender</h1><p className="eyebrow">Nächste 7 Tage · {calendarStatus}</p></div>
            <button className="refresh-button" disabled={calendarRefreshing} onClick={() => loadCalendar(true)}>{calendarRefreshing ? 'Aktualisiere…' : 'Aktualisieren'}</button>
          </div>
          <div className="calendar-week">
            {calendarDays.map((day) => (
              <article className={`calendar-day${day.key === todayLocal ? ' today' : ''}`} key={day.key}>
                <header><b>{day.date.toLocaleDateString('de-DE', { weekday: 'short' })}</b><span>{day.date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' })}</span></header>
                <div className="calendar-events">
                  {day.items.map((item) => (
                    <button className="calendar-event" key={`${item.start}-${item.title}-${item.calendarName}`}>
                      <small>{item.all_day ? 'Ganztägig' : new Date(item.start).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}</small>
                      <b>{item.title}</b>
                      {item.location && <span>{item.location}</span>}
                      {item.calendarName && <em>{item.calendarName}</em>}
                    </button>
                  ))}
                  {day.items.length === 0 && <span className="calendar-empty">—</span>}
                </div>
              </article>
            ))}
          </div>
        </section>}

        {page === 'timer' && <section className="timer-view">
          <div>
            <div className="timer-mode-switch"><button className={timerMode === 'timer' ? 'active' : ''} onClick={() => chooseTimerMode('timer')}>Normaler Timer</button><button className={timerMode === 'pomodoro' ? 'active' : ''} onClick={() => chooseTimerMode('pomodoro')}>Pomodoro</button></div>
            <small>{timerMode === 'pomodoro' ? timerPhase === 'work' ? 'ARBEITSPHASE' : 'PAUSE' : 'TIMER'}</small>
            <strong>{timer}</strong>
            {timerMode === 'timer' ? <div className="timer-adjust"><button aria-label="Eine Minute abziehen" onClick={() => changeWorkMinutes(workMinutes - 1)}>−</button><span>{workMinutes} Minuten</span><button aria-label="Eine Minute hinzufügen" onClick={() => changeWorkMinutes(workMinutes + 1)}>+</button></div> : <div className="pomodoro-meta"><span>{pomodoroCount % 4}/4 Durchgänge</span><b>{timerPhase === 'work' ? workMinutes : breakMinutes} Min.</b></div>}
          </div>
          <BuddyFace mood={mood} onClick={() => triggerAvatar('user_clicked_avatar', 'Der Benutzer hat den Timer-Avatar berührt')} />
          <div className="timer-actions"><button onClick={() => { if (!running) triggerAvatar('timer_started', timerMode === 'pomodoro' ? 'Pomodoro gestartet' : 'Timer gestartet'); setRunning((value) => !value) }}>{running ? 'Pause' : secondsLeft === 0 ? 'Neu starten' : 'Start'}</button><button className="round-action" onClick={() => { setRunning(false); setTimerPhase('work'); setSecondsLeft(workMinutes * 60) }}><TimerReset size={22} /></button></div>
        </section>}

        {page === 'config' && <section className="page-view settings">
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
          <div className="setting-row icloud-setting">
            <span><b>iCloud-Kalender</b><small>{calendarStatus}</small></span>
            <div className="icloud-config">
              <input aria-label="Apple-ID" placeholder="Apple-ID / E-Mail" value={icloudUsername} onChange={(event) => setIcloudUsername(event.target.value)} />
              <input aria-label="App-spezifisches Passwort" type="password" placeholder="App-Passwort" value={icloudPassword} onChange={(event) => setIcloudPassword(event.target.value)} />
              <div className="calendar-checklist" aria-label="Angezeigte iCloud-Kalender">
                {icloudCalendars.map((item) => (
                  <label key={item.url}>
                    <input
                      type="checkbox"
                      checked={icloudCalendarUrls.includes(item.url)}
                      onChange={(event) => setIcloudCalendarUrls((current) => event.target.checked ? [...current, item.url] : current.filter((url) => url !== item.url))}
                    />
                    <span>{item.name}</span>
                  </label>
                ))}
                {icloudCalendars.length === 0 && <span>Keine Kalender geladen</span>}
              </div>
              <button onClick={saveIcloudCalendar}>Speichern</button>
            </div>
          </div>
          <div className="setting-row night-setting">
            <span><b>Nachtmodus</b><small>Display automatisch ausschalten</small></span>
            <button className={`switch${nightEnabled ? ' on' : ''}`} aria-label="Nachtmodus" onClick={() => { setNightEnabled((value) => { void saveSetting('nightEnabled', String(!value)); return !value }) }}><i /></button>
            <div className="night-times">
              <label><small>Aus</small><input type="time" value={nightStart} onChange={(event) => { setNightStart(event.target.value); void saveSetting('nightStart', event.target.value) }} /></label>
              <label><small>An</small><input type="time" value={nightEnd} onChange={(event) => { setNightEnd(event.target.value); void saveSetting('nightEnd', event.target.value) }} /></label>
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
            <button onClick={() => { if (!running) triggerAvatar('timer_started', 'Timer über Schnellmenü gestartet'); setRunning((value) => !value); setQuickMenuOpen(false) }}>
              <TimerReset size={20} /><span>{running ? 'Timer pausieren' : 'Timer starten'}</span>
            </button>
            <button onClick={() => { loadTasks(); setQuickMenuOpen(false) }}>
              <RefreshCw size={20} /><span>Aktualisieren</span>
            </button>
            <button onClick={sleepDisplay}>
              <Power size={20} /><span>Display aus</span>
            </button>
          </div>
        </section>
      </>}

      {!standaloneConfig && <nav className="nav-bar" aria-label="Hauptnavigation">
        <button className={page === 'home' ? 'active' : ''} onClick={() => setPage('home')}><Home size={21} /><span>Home</span></button>
        <button className={page === 'tasks' ? 'active' : ''} onClick={() => setPage('tasks')}><ListTodo size={21} /><span>Aufgaben</span></button>
        <button className={page === 'calendar' ? 'active' : ''} onClick={() => setPage('calendar')}><CalendarDays size={21} /><span>Kalender</span></button>
        <button className={page === 'timer' ? 'active' : ''} onClick={() => setPage('timer')}><Coffee size={21} /><span>Timer</span></button>
      </nav>}
    </main>
  )
}

export default App
