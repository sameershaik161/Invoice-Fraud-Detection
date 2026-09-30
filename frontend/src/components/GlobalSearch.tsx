import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Loader2, ArrowUp, ArrowDown, CornerDownLeft } from 'lucide-react'
import { getGlobalSearch } from '@/services/api'
import type { SearchResultItem } from '@/types'

const GROUP_ORDER: SearchResultItem['type'][] = ['INVOICES', 'COMPANIES', 'LENDERS', 'DELIVERY PROOFS']
const RECENT_SEARCH_KEY = 'ifg.recent-searches'

export default function GlobalSearch() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResultItem[]>([])
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState(false)
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [recentSearches, setRecentSearches] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(RECENT_SEARCH_KEY) ?? '[]') as string[]
    } catch {
      return []
    }
  })

  const orderedResults = GROUP_ORDER.flatMap((type) => results.filter((item) => item.type === type))
  const shortcutLabel = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K'

  useEffect(() => {
    const onShortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen(true)
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onShortcut)
    return () => window.removeEventListener('keydown', onShortcut)
  }, [])

  useEffect(() => {
    const value = query.trim()
    if (!value || value.length < 2) {
      setResults([])
      setSearchError(false)
      setActiveIndex(-1)
      return
    }

    const timer = setTimeout(() => {
      setLoading(true)
      setSearchError(false)
      getGlobalSearch(value)
        .then((res) => {
          setResults(res.data.results ?? [])
          setOpen(true)
          setActiveIndex(-1)
        })
        .catch(() => { setResults([]); setSearchError(true); setOpen(true) })
        .finally(() => setLoading(false))
    }, 300)

    return () => clearTimeout(timer)
  }, [query])

  const handleSelect = (item: SearchResultItem) => {
    const recent = [query.trim() || item.label, ...recentSearches.filter((term) => term !== (query.trim() || item.label))].slice(0, 5)
    setRecentSearches(recent)
    localStorage.setItem(RECENT_SEARCH_KEY, JSON.stringify(recent))
    setOpen(false)
    setQuery('')
    navigate(item.route || '/invoices')
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setOpen(false)
    } else if (event.key === 'ArrowDown' && open && orderedResults.length) {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % orderedResults.length)
    } else if (event.key === 'ArrowUp' && open && orderedResults.length) {
      event.preventDefault()
      setActiveIndex((index) => index <= 0 ? orderedResults.length - 1 : index - 1)
    } else if (event.key === 'Enter' && activeIndex >= 0 && orderedResults[activeIndex]) {
      event.preventDefault()
      handleSelect(orderedResults[activeIndex])
    }
  }

  return (
    <div className="relative w-full max-w-xl">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          ref={inputRef}
          id="global-search"
          className="input w-full pl-9 pr-10"
          placeholder="Search invoice, GSTIN, company, lender..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls="global-search-results"
        />
        {loading && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          </span>
        )}
        {!loading && !query && <kbd className="absolute right-3 top-1/2 -translate-y-1/2 rounded border border-surface-700 px-1.5 py-0.5 text-[10px] text-slate-500">{shortcutLabel}</kbd>}
      </div>

      {open && (
        <div id="global-search-results" role="listbox" aria-label="Search suggestions" className="absolute z-50 mt-2 max-h-[min(70vh,28rem)] w-full overflow-y-auto rounded-md border border-surface-700 bg-white shadow-xl">
          {loading && <div className="flex items-center gap-2 px-4 py-3 text-xs text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" />Searching project records</div>}
          {searchError && <div role="status" className="px-4 py-3 text-sm text-red-800">Search is unavailable. Check the API connection and try again.</div>}
          {!loading && !searchError && query.trim().length >= 2 && orderedResults.length === 0 && <div role="status" className="px-4 py-4"><div className="text-sm font-medium text-slate-800">No matching records</div><div className="mt-1 text-xs text-slate-500">No results were returned for “{query.trim()}”.</div></div>}
          {!query.trim() && recentSearches.length > 0 && <div className="border-b border-surface-700 px-3 py-2"><div className="mb-1 px-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Recent selections</div>{recentSearches.map((term) => <button key={term} role="option" aria-selected="false" className="block w-full rounded px-2 py-1.5 text-left text-xs text-slate-700 hover:bg-surface-800" onMouseDown={(event) => event.preventDefault()} onClick={() => setQuery(term)}>{term}</button>)}</div>}
          {orderedResults.map((item, index) => {
            const previous = orderedResults[index - 1]
            return <div key={`${item.type}-${item.id}`}>
              {(!previous || previous.type !== item.type) && <div className="px-4 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-500">{item.type}</div>}
              <button
                id={`global-result-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                className={`flex w-full items-center justify-between gap-3 px-4 py-2 text-left ${index === activeIndex ? 'bg-blue-50' : 'hover:bg-surface-800'}`}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => handleSelect(item)}
              >
                <span className="min-w-0"><span className="block truncate text-sm font-medium text-slate-900">{item.label}</span><span className="mt-0.5 block truncate text-[11px] text-slate-500">{item.subtitle}</span></span>
                {index === activeIndex ? <CornerDownLeft className="h-3.5 w-3.5 shrink-0 text-blue-800" /> : <span className="text-[10px] text-slate-500">Open</span>}
              </button>
            </div>
          })}
          {orderedResults.length > 0 && <div className="flex items-center gap-3 border-t border-surface-700 px-4 py-2 text-[10px] text-slate-500"><span className="inline-flex items-center gap-1"><ArrowUp className="h-3 w-3" /><ArrowDown className="h-3 w-3" /> Navigate</span><span><CornerDownLeft className="mr-1 inline h-3 w-3" />Open record</span><span>Esc Close</span></div>}
        </div>
      )}
    </div>
  )
}
