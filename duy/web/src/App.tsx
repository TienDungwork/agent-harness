import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

type AskResponse = {
  question: string
  answer: string
  intent?: string | null
  intent_reason?: string | null
  sql?: string | null
  database?: string | null
  row_count?: number | null
  error?: string | null
  doc_card_id?: string | null
  doc_card_title?: string | null
  chart_png_base64?: string | null
  chart_meta?: string | null
  web_sources?: { title: string; url: string }[] | null
  llm_model_id?: string | null
  llm_model_label?: string | null
}

type ModelOption = {
  id: string
  label: string
  model: string
}

const EXAMPLES = [
  'Có bao nhiêu camera đang hoạt động?',
  'Làm sao để thêm camera?',
  'ALPR là gì?',
]

const INTENT_LABEL: Record<string, string> = {
  query_db: 'Truy vấn DB',
  how_to: 'Hướng dẫn',
  troubleshoot: 'Xử lý sự cố',
  concept: 'Khái niệm',
  chat: 'Hội thoại',
  clarify: 'Cần làm rõ',
  out_of_scope: 'Ngoài phạm vi',
  web_search: 'Tìm web',
}

const MODEL_STORAGE_KEY = 'duy.model_id'

export default function App() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [result, setResult] = useState<AskResponse | null>(null)
  const [fail, setFail] = useState<string | null>(null)
  const [showSql, setShowSql] = useState(false)
  const [models, setModels] = useState<ModelOption[]>([])
  const [modelId, setModelId] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadModels() {
      try {
        const res = await fetch('/api/models')
        if (!res.ok) return
        const data = await res.json()
        const list = (data.models || []) as ModelOption[]
        if (cancelled || !list.length) return
        setModels(list)
        const saved = localStorage.getItem(MODEL_STORAGE_KEY) || ''
        const ids = new Set(list.map((m) => m.id))
        const next =
          (saved && ids.has(saved) && saved) ||
          (data.default_id && ids.has(data.default_id) && data.default_id) ||
          list[0].id
        setModelId(next)
      } catch {
        // giữ trống — API sẽ dùng default
      }
    }
    void loadModels()
    return () => {
      cancelled = true
    }
  }, [])

  function onModelChange(id: string) {
    setModelId(id)
    localStorage.setItem(MODEL_STORAGE_KEY, id)
  }

  async function submit(q: string) {
    const trimmed = q.trim()
    if (!trimmed || loading) return

    setLoading(true)
    setFail(null)
    setResult(null)
    setShowSql(false)
    setStatus('Đang gửi…')

    try {
      const res = await fetch('/api/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: trimmed,
          model_id: modelId || undefined,
        }),
      })
      if (!res.ok || !res.body) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail || `Lỗi HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let draft: AskResponse = {
        question: trimmed,
        answer: '',
        intent: null,
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() || ''

        for (const chunk of chunks) {
          const line = chunk
            .split('\n')
            .map((l) => l.trim())
            .find((l) => l.startsWith('data:'))
          if (!line) continue
          const raw = line.slice(5).trim()
          let event: Record<string, unknown>
          try {
            event = JSON.parse(raw)
          } catch {
            continue
          }

          const type = String(event.type || '')
          if (type === 'status') {
            setStatus(String(event.message || ''))
          } else if (type === 'model') {
            draft = {
              ...draft,
              llm_model_id: String(event.model_id || ''),
              llm_model_label: String(event.model_label || ''),
            }
            setResult({ ...draft })
          } else if (type === 'intent') {
            draft = {
              ...draft,
              intent: String(event.intent || ''),
              intent_reason: String(event.intent_reason || ''),
            }
            setResult({ ...draft })
          } else if (type === 'answer') {
            draft = { ...draft, answer: String(event.text || '') }
            setResult({ ...draft })
          } else if (type === 'chart') {
            draft = {
              ...draft,
              chart_png_base64: String(event.chart_png_base64 || ''),
              chart_meta: String(event.chart_meta || ''),
            }
            setResult({ ...draft })
          } else if (type === 'web_sources') {
            draft = {
              ...draft,
              web_sources: (event.sources as { title: string; url: string }[]) || [],
            }
            setResult({ ...draft })
          } else if (type === 'done') {
            const r = (event.result || {}) as AskResponse
            draft = { ...draft, ...r }
            setResult(draft)
            setStatus(null)
          } else if (type === 'error') {
            throw new Error(String(event.message || 'Lỗi stream'))
          }
        }
      }
    } catch (err) {
      setFail(err instanceof Error ? err.message : 'Không gọi được API')
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void submit(question)
  }

  const usedSql = Boolean(result?.sql && result.intent === 'query_db')
  const usedDocs = Boolean(
    result?.doc_card_id &&
      (result.intent === 'how_to' ||
        result.intent === 'troubleshoot' ||
        result.intent === 'concept'),
  )
  const usedWeb = Boolean(
    result?.intent === 'web_search' && (result.web_sources?.length || 0) > 0,
  )

  return (
    <div className="shell">
      <header className="brand-block">
        <p className="brand">DUY</p>
        <h1>Hỏi dữ liệu VMS</h1>
        <p className="lede">
          Số liệu DB, hướng dẫn VMS, tìm kiếm web, hoặc biểu đồ từ truy vấn.
        </p>
      </header>

      <form className="composer" onSubmit={onSubmit}>
        {models.length > 0 && (
          <div className="model-row">
            <label htmlFor="model">Model</label>
            <select
              id="model"
              value={modelId}
              disabled={loading}
              onChange={(e) => onModelChange(e.target.value)}
            >
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>
        )}
        <label className="sr-only" htmlFor="q">
          Câu hỏi
        </label>
        <textarea
          id="q"
          ref={inputRef}
          rows={3}
          value={question}
          disabled={loading}
          placeholder="Xin chào, hoặc hỏi số liệu camera / sự kiện…"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void submit(question)
            }
          }}
        />
        <div className="composer-bar">
          <p className="hint">Enter gửi · Shift+Enter xuống dòng</p>
          <button type="submit" disabled={loading || !question.trim()}>
            {loading ? 'Đang xử lý…' : 'Gửi'}
          </button>
        </div>
      </form>

      <div className="examples" aria-label="Câu hỏi gợi ý">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            className="example"
            disabled={loading}
            onClick={() => {
              setQuestion(ex)
              void submit(ex)
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      {loading && status && (
        <div className="status" role="status">
          <span className="dot" />
          {status}
        </div>
      )}

      {fail && (
        <div className="result err" role="alert">
          <p className="result-label">Không kết nối được</p>
          <p>{fail}</p>
          <p className="meta">Chạy API: <code>uv run agent-serve</code></p>
        </div>
      )}

      {result && (result.answer || result.intent) && (
        <section className="result" aria-live="polite">
          <p className="result-label">Trả lời</p>
          <p className="answer">{result.answer || (loading ? '…' : '')}</p>

          {result.chart_png_base64 && (
            <figure className="chart">
              <img
                src={`data:image/png;base64,${result.chart_png_base64}`}
                alt="Biểu đồ từ kết quả truy vấn"
              />
              {result.chart_meta && (
                <figcaption>{result.chart_meta}</figcaption>
              )}
            </figure>
          )}

          <div className="meta-row">
            {result.llm_model_label && <span>{result.llm_model_label}</span>}
            {result.intent && (
              <span>{INTENT_LABEL[result.intent] || result.intent}</span>
            )}
            {usedSql && result.database && <span>DB · {result.database}</span>}
            {usedSql && typeof result.row_count === 'number' && (
              <span>{result.row_count} dòng</span>
            )}
            {usedDocs && result.doc_card_title && (
              <span>Tài liệu · {result.doc_card_title}</span>
            )}
            {usedWeb && <span>Web · SearXNG</span>}
            {usedSql && result.sql && (
              <button
                type="button"
                className="linkish"
                onClick={() => setShowSql((v) => !v)}
              >
                {showSql ? 'Ẩn SQL' : 'Xem SQL'}
              </button>
            )}
          </div>

          {showSql && usedSql && result.sql && (
            <pre className="sql">
              <code>{result.sql}</code>
            </pre>
          )}

          {usedWeb && result.web_sources && (
            <ul className="web-sources">
              {result.web_sources.map((src) => (
                <li key={src.url}>
                  <a href={src.url} target="_blank" rel="noreferrer">
                    {src.title || src.url}
                  </a>
                </li>
              ))}
            </ul>
          )}

          {result.error && (
            <p className="warn">Chi tiết lỗi: {result.error}</p>
          )}
        </section>
      )}

      <footer className="foot">
        Local · Remote LLM · LangGraph · Postgres read-only
      </footer>
    </div>
  )
}
