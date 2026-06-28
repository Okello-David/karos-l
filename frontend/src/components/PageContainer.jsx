export default function PageContainer({ title, description, children }) {
  return (
    <div className="p-4 lg:p-8 space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl lg:text-3xl font-bold text-gray-900">{title}</h1>
        {description && (
          <p className="mt-2 text-gray-600 text-lg leading-relaxed">{description}</p>
        )}
      </div>
      {children}
    </div>
  )
}
