import { useEffect, useState } from 'react'
import './UploadTabModal.css'

type UploadTabModalProps = {
  isOpen: boolean
  onClose: () => void
}

type SongLookupResponse = {
  status: 'ok' | 'unsupported' | 'invalid'
  source?: string
  message?: string
  match?: {
    title?: string
    composer?: string
    score_url?: string
    file_format?: string
  }
  tab?: {
    ascii: string
    events: Array<{ pitch: number; start: number; duration: number; fret: number; string: number }>
  }
}

const newbecBaseUrl = (import.meta.env.VITE_NEWBEC_BASE_URL?.trim() || 'http://127.0.0.1:8000').replace(/\/$/, '')

export function UploadTabModal({ isOpen, onClose }: UploadTabModalProps) {
  const [title, setTitle] = useState('')
  const [result, setResult] = useState<SongLookupResponse | undefined>()
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState<string | undefined>()

  useEffect(() => {
    if (!isOpen) {
      setTitle('')
      setResult(undefined)
      setError(undefined)
      setIsSearching(false)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedTitle = title.trim()
    if (!normalizedTitle || isSearching) return

    setError(undefined)
    setResult(undefined)
    setIsSearching(true)
    try {
      const response = await fetch(`${newbecBaseUrl}/api/song?title=${encodeURIComponent(normalizedTitle)}`)
      const payload = await response.json() as SongLookupResponse
      if (!response.ok && payload.status !== 'unsupported') {
        throw new Error(payload.message || 'Не удалось выполнить поиск')
      }
      setResult(payload)
    } catch (lookupError) {
      setError(lookupError instanceof Error ? lookupError.message : 'Не удалось связаться с сервисом поиска')
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <div className="upload-modal-backdrop" role="presentation" onMouseDown={() => !isSearching && onClose()}>
      <section
        className="upload-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="upload-tab-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="upload-modal-heading">
          <div>
            <p className="upload-modal-eyebrow">Новая табулатура</p>
            <h2 id="upload-tab-title">Найти песню</h2>
          </div>
          <button className="upload-modal-close" type="button" onClick={onClose} disabled={isSearching} aria-label="Закрыть окно">×</button>
        </div>

        <form className="upload-modal-form" onSubmit={(event) => void handleSubmit(event)}>
          <label className="song-title-field">
            <span>Название песни</span>
            <input
              autoFocus
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Например: Moonlight Sonata guitar или Sor Opus 1"
              disabled={isSearching}
            />
            <small>Ищем гитарные ноты и MIDI в подключённых каталогах.</small>
          </label>

          {isSearching && <p className="upload-progress" aria-live="polite">Ищем произведение и доступные ноты…</p>}
          {error && <p className="upload-error" role="alert">{error}</p>}
          {result && <SongLookupResult result={result} />}

          <div className="upload-modal-actions">
            <button className="upload-cancel" type="button" onClick={onClose} disabled={isSearching}>Отмена</button>
            <button className="upload-submit" type="submit" disabled={!title.trim() || isSearching}>
              {isSearching ? 'Ищем…' : 'Найти ноты'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}

function SongLookupResult({ result }: { result: SongLookupResponse }) {
  if (result.status === 'ok' && result.tab) {
    return (
      <div className="song-lookup-result song-lookup-success" aria-live="polite">
        <strong>Ноты найдены</strong>
        <span>Источник: {result.source}{result.match?.title ? ` · ${result.match.title}` : ''}</span>
        <pre>{result.tab.ascii}</pre>
        <small>Событий нот: {result.tab.events.length}. Табулатура построена автоматически.</small>
      </div>
    )
  }

  return (
    <div className="song-lookup-result song-lookup-empty" role="status">
      <strong>Песня пока не поддерживается</strong>
      <span>{result.message || 'В доступных источниках нет машинно читаемых нот.'}</span>
    </div>
  )
}
