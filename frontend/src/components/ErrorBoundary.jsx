import { Component } from 'react'
import Button from './Button'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <p className="text-7xl font-bold text-gray-200 mb-4">!</p>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">Something went wrong</h1>
            <p className="text-gray-600 mb-2">
              An unexpected error occurred. Please try again.
            </p>
            {this.state.error && (
              <p className="text-sm text-red-500 mb-8 font-mono bg-red-50 p-3 rounded-lg">
                {this.state.error.message}
              </p>
            )}
            <div className="flex justify-center gap-3">
              <Button onClick={this.handleReset}>Try Again</Button>
              <Button
                variant="secondary"
                onClick={() => window.location.href = '/'}
              >
                Go to Overview
              </Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
