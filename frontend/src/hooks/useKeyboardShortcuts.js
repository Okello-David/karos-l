import { useEffect } from 'react'

export function useKeyboardShortcuts(shortcuts, enabled = true) {
  useEffect(() => {
    if (!enabled) return

    function handler(e) {
      if (
        e.target.tagName === 'INPUT' ||
        e.target.tagName === 'TEXTAREA' ||
        e.target.isContentEditable
      ) {
        if (e.key === 'Escape') {
          const active = document.activeElement
          if (active) active.blur()
        }
        return
      }

      for (const shortcut of shortcuts) {
        const { key, ctrl = false, shift = false, alt = false, action } = shortcut
        if (
          e.key === key &&
          e.ctrlKey === ctrl &&
          e.shiftKey === shift &&
          e.altKey === alt
        ) {
          e.preventDefault()
          e.stopPropagation()
          action(e)
          return
        }
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [shortcuts, enabled])
}
