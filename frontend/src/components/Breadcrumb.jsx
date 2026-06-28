import { Link } from 'react-router-dom'

export default function Breadcrumb({ items }) {
  return (
    <nav className="flex items-center gap-2 text-xs text-gray-400 mt-0.5" aria-label="Breadcrumb">
      <Link to="/" className="hover:text-gray-600 transition-colors">
        Home
      </Link>
      {items.map((item, index) => (
        <span key={index} className="flex items-center gap-2">
          <span>/</span>
          {item.path ? (
            <Link to={item.path} className="hover:text-gray-600 transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-gray-700">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
