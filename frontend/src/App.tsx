import { NavLink, Route, Routes } from 'react-router-dom'
import { CorpusPage } from './pages/CorpusPage'
import { SearchPage } from './pages/SearchPage'

export default function App() {
  return (
    <div className="app-shell">
      <nav className="top-nav">
        <div className="brand">Vectorless RAG</div>
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          Search
        </NavLink>
        <NavLink to="/corpus" className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
          Corpus
        </NavLink>
      </nav>
      <main>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/corpus" element={<CorpusPage />} />
        </Routes>
      </main>
    </div>
  )
}
