export function Skeleton({ className = '' }) {
  return (
    <div className={`animate-pulse bg-gray-100 rounded ${className}`} />
  )
}

export function TableSkeleton({ rows = 5, cols = 4 }) {
  return (
    <div className="space-y-3">
      <div className="flex gap-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-4">
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} className={`h-10 flex-1 ${c === 0 ? '' : 'hidden sm:block'}`} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton({ count = 3, height = 'h-32' }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="bg-white rounded-xl border border-gray-200 p-6">
          <Skeleton className="h-4 w-1/3 mb-4" />
          <Skeleton className={`${height} w-full`} />
        </div>
      ))}
    </div>
  )
}
